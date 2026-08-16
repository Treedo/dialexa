"""ASR-потік: faster-whisper (німецька) по висловлюваннях з контекстом попереднього тексту."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

log = logging.getLogger(__name__)

# Короткий німецький підказковий текст: зміщує декодер у домен лекції
# та зменшує галюциновані вступи («Дякую за перегляд...» тощо).
INITIAL_PROMPT = (
    "Das ist eine Vorlesung an der Universität. "
    "Der Professor spricht langsam und deutlich über das Thema."
)


class _TimeWindow:
    """Ковзне вікно (початок, тривалість) для підрахунку завантаженості."""

    def __init__(self, maxlen: int = 200):
        self._items: deque[tuple[float, float]] = deque(maxlen=maxlen)

    def add(self, start: float, duration: float) -> None:
        self._items.append((start, duration))

    def fraction(self) -> float:
        """Частка часу, зайнятого роботою, у ковзному вікні (0..1)."""
        if len(self._items) < 2:
            return 0.0
        span = self._items[-1][0] - self._items[0][0]
        if span <= 0:
            return 0.0
        busy = sum(d for _, d in self._items)
        return min(1.0, busy / span)


class ASRWorker(threading.Thread):
    """Споживає висловлювання з asr_queue; результат — у bus і mt_queue."""

    def __init__(
        self,
        asr_queue,
        mt_queue,
        bus,
        settings,
        whisper_dir,
        ready_event: threading.Event,
        stop_event: threading.Event,
        on_utterance=None,  # опц. колбек (utt_id, t_end, t_german) для статистики
    ):
        super().__init__(daemon=True, name="asr")
        self.asr_queue = asr_queue
        self.mt_queue = mt_queue
        self.bus = bus
        self.settings = settings
        self.whisper_dir = whisper_dir
        self.ready_event = ready_event
        self.stop_event = stop_event
        self.on_utterance = on_utterance
        self.busy_window = _TimeWindow()
        self._reset_context_flag = threading.Event()
        self._active = 0
        self._active_lock = threading.Lock()

    def active_count(self) -> int:
        """Скільки висловлювань зараз у обробці (для очікування завершення)."""
        with self._active_lock:
            return self._active

    def reset_context(self) -> None:
        """Скинути попередній текст (при паузі/резюме). Безпечно з будь-якого потоку."""
        self._reset_context_flag.set()

    def run(self) -> None:
        self.ready_event.wait()
        if self.stop_event.is_set():
            return
        from faster_whisper import WhisperModel  # лінивий імпорт

        try:
            model = WhisperModel(
                str(self.whisper_dir),
                device="cpu",
                compute_type="int8",
                cpu_threads=self.settings.asr_cpu_threads,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("whisper load failed")
            self.bus.status.emit(f"Помилка завантаження моделі розпізнавання: {e}")
            return
        self.bus.status.emit("✅ Розпізнавання німецької готове")

        previous_text = ""
        last_text = ""
        repeat_count = 0

        while not self.stop_event.is_set():
            try:
                utt = self.asr_queue.get(timeout=0.5)
            except Exception:  # queue.Empty
                continue
            if self._reset_context_flag.is_set():
                self._reset_context_flag.clear()
                previous_text = ""
                last_text = ""
                repeat_count = 0

            with self._active_lock:
                self._active += 1
            t0 = time.perf_counter()
            try:
                segments, _info = model.transcribe(
                    utt.audio,
                    language="de",
                    beam_size=self.settings.asr_beam_size,
                    temperature=0.0,
                    condition_on_previous_text=bool(previous_text),
                    initial_prompt=INITIAL_PROMPT,
                    vad_filter=False,  # VAD уже зроблений нашим сегментатором
                    without_timestamps=True,
                )
                # УВАГА: transcribe() лінивий — реальне декодування відбувається
                # при ітерації segments, тому споживаємо генератор УСЕРЕДИНІ try,
                # щоб active_count() відображав фактичну роботу.
                text = " ".join(s.text.strip() for s in segments).strip()
            except Exception as e:  # noqa: BLE001
                log.exception("transcribe failed")
                self.bus.status.emit(f"Помилка розпізнавання: {e}")
                continue
            finally:
                with self._active_lock:
                    self._active -= 1
            self.busy_window.add(t0, time.perf_counter() - t0)
            if not text:
                continue

            # Guard галюцинацій: той самий короткий текст 3× поспіль — придушити
            if text == last_text and len(text) < 60:
                repeat_count += 1
            else:
                repeat_count = 0
            last_text = text
            if repeat_count >= 3:
                log.info("hallucination guard: suppressed %r", text[:50])
                previous_text = ""
                repeat_count = 0
                continue

            previous_text = (previous_text + " " + text)[
                -self.settings.asr_previous_text_max_chars :
            ]
            self.bus.german_utterance.emit(utt.id, text)
            if self.on_utterance is not None:
                self.on_utterance(utt.id, utt.t_end, time.time())
            self.mt_queue.put((utt.id, text))
