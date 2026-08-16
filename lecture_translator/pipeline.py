"""Pipeline: життєвий цикл потоків і черг.

    [audio] -> vad_q -> [VAD+Silero] -> asr_q -> [faster-whisper] -> mt_q -> [NLLB]
                                                      |-> bus.german_utterance
                                                                       |-> bus.sentence_translated

Правила:
  - vad_q — звичайна блокуюча черга (backpressure; VAD завжди швидший за аудіо);
  - asr_q та mt_q — DropOldestQueue(4): відставання гаситься пропуском старого,
    а не накопиченням хвилин затримки;
  - робочі потоки спілкуються з UI ТІЛЬКИ через bus (Qt-сигнали).
"""
from __future__ import annotations

import logging
import queue
import threading
import time

import numpy as np

from .asr.worker import ASRWorker
from .audio.capture import AudioCapture
from .config import Settings, models_dir
from .models import ModelManager
from .queues import DropOldestQueue, RingBuffer
from .translate.worker import TranslationWorker
from .vad.segmenter import Segmenter
from .vad.vad_model import SileroVAD, WINDOW_SAMPLES, ensure_silero_model
from .vad.worker import VADWorker
from .watchdog import Watchdog

log = logging.getLogger(__name__)

VAD_QUEUE_SIZE = 512  # блоків ~32 мс ≈ 16 с
WORKER_QUEUE_SIZE = 4  # висловлювань


class FileSource(threading.Thread):
    """Режим --file: читає WAV/MP3/... через PyAV замість пристрою.

    Декодує у 16 кГц моно float32 і подає у vad_q вікнами по 512 семплів
    з реальним темпом (speed=1.0) або без пауз (speed=0).
    """

    def __init__(self, path: str, vad_queue: queue.Queue, speed: float, stop_event: threading.Event):
        super().__init__(daemon=True, name="file-source")
        self.path = path
        self.vad_queue = vad_queue
        self.speed = speed
        self.stop_event = stop_event

    def run(self) -> None:
        import av  # лінивий імпорт (важка бібліотека)

        container = av.open(self.path)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
        try:
            for frame in container.decode(audio=0):
                if self.stop_event.is_set():
                    return
                for fr in resampler.resample(frame):
                    arr = fr.to_ndarray().reshape(-1).astype(np.float32)
                    for i in range(0, arr.size, WINDOW_SAMPLES):
                        chunk = arr[i : i + WINDOW_SAMPLES]
                        if chunk.size < WINDOW_SAMPLES:  # хвіст файлу — доповнюємо тишею
                            chunk = np.pad(chunk, (0, WINDOW_SAMPLES - chunk.size))
                        self.vad_queue.put(chunk)
                        if self.speed > 0 and not self.stop_event.is_set():
                            time.sleep(WINDOW_SAMPLES / 16000 * self.speed)
        finally:
            container.close()


class Pipeline:
    def __init__(self, bus, settings: Settings):
        self.bus = bus
        self.settings = settings
        self.vad_q: queue.Queue = queue.Queue(maxsize=VAD_QUEUE_SIZE)
        self.asr_q = DropOldestQueue(WORKER_QUEUE_SIZE)
        self.mt_q = DropOldestQueue(WORKER_QUEUE_SIZE)
        self.ring = RingBuffer()
        self.model_manager = ModelManager(bus)
        self.ready_event = threading.Event()
        self.stop_event = threading.Event()
        self.capture_stop = threading.Event()
        self.vad_flush = threading.Event()
        self.file_done = threading.Event()
        self.running = False
        self.paused = False
        self.current_device: str | None = None
        self.stats = None  # StatsCollector (--file --stats)
        self._threads: list[threading.Thread] = []
        self._capture: AudioCapture | None = None
        self._vad_worker: VADWorker | None = None
        self.asr_worker: ASRWorker | None = None
        self.mt_worker: TranslationWorker | None = None

    # ---------- запуск ----------

    def start(self, device_id: str | None = None) -> None:
        if self.running:
            return
        self.running = True
        self.stop_event.clear()
        self.capture_stop.clear()
        self.vad_flush.clear()
        self.file_done.clear()
        self.ready_event.clear()  # при рестарті (нова модель) завантажувач знову set його
        self.current_device = device_id
        self._start_core()
        self._start_capture_and_vad(device_id)

    def start_file(self, path: str, speed: float = 1.0, stats=None) -> None:
        """Режим тестування з файлу (без пристрою)."""
        self.stats = stats
        self.running = True
        self.stop_event.clear()
        self.vad_flush.clear()
        self.file_done.clear()
        self.ready_event.clear()
        self._start_core()
        self._start_vad()
        source = FileSource(path, self.vad_q, speed, self.stop_event)
        source.start()
        self._threads.append(source)
        threading.Thread(
            target=self._watch_file_done, args=(source,), daemon=True, name="file-done-watch"
        ).start()

    def _start_core(self) -> None:
        """Завантажувач моделей + робочі потоки (спільне для пристрою і файлу)."""
        t = threading.Thread(
            target=self.model_manager.ensure_all,
            args=(self.settings, self.ready_event),
            daemon=True,
            name="model-downloader",
        )
        t.start()
        self._threads.append(t)

        whisper_dir = self.model_manager.whisper_dir(self.settings.asr_model)
        self.asr_worker = ASRWorker(
            self.asr_q, self.mt_q, self.bus, self.settings,
            whisper_dir, self.ready_event, self.stop_event,
            on_utterance=(lambda uid, te, tg: self.stats.on_utterance(uid, te, tg))
            if self.stats else None,
        )
        self.mt_worker = TranslationWorker(
            self.mt_q, self.bus, self.settings, self.model_manager,
            self.ready_event, self.stop_event,
            on_translated=(lambda uid, t: self.stats.on_translated(uid, t))
            if self.stats else None,
        )
        self.asr_worker.start()
        self.mt_worker.start()
        self._threads += [self.asr_worker, self.mt_worker]

        watchdog = Watchdog(
            self.bus, self.asr_worker, self.mt_worker, self.asr_q, self.stop_event
        )
        watchdog.start()
        self._threads.append(watchdog)

    def _start_vad(self) -> None:
        try:
            model_path = ensure_silero_model(models_dir())
            vad_model = SileroVAD(model_path)
        except Exception as e:  # noqa: BLE001
            log.exception("silero init failed")
            self.bus.status.emit(f"Помилка ініціалізації VAD: {e}")
            return
        seg = Segmenter(
            threshold=self.settings.vad_threshold,
            min_speech_ms=self.settings.vad_min_speech_ms,
            silence_ms=self.settings.vad_silence_ms,
            pad_ms=self.settings.vad_pad_ms,
            max_utterance_ms=self.settings.vad_max_utterance_ms,
        )
        self._vad_worker = VADWorker(
            self.vad_q, self.asr_q, seg, vad_model, self.bus,
            self.stop_event, self.vad_flush,
        )
        self._vad_worker.start()
        self._threads.append(self._vad_worker)

    def _start_capture_and_vad(self, device_id: str | None) -> None:
        self._start_vad()
        self._capture = AudioCapture(
            self.bus, device_id, self.vad_q, self.ring, self.capture_stop
        )
        self._capture.start()
        self._threads.append(self._capture)

    def _idle(self) -> bool:
        """Черги порожні і нічого не обробляється зараз (ASR/переклад)."""
        return (
            self.asr_q.qsize() == 0
            and self.mt_q.qsize() == 0
            and self.asr_worker is not None
            and self.asr_worker.active_count() == 0
            and self.mt_worker is not None
            and self.mt_worker.active_count() == 0
        )

    def _watch_file_done(self, source: FileSource) -> None:
        source.join()
        # кінець файлу: зливаємо хвіст у сегментаторі VAD і чекаємо його виходу —
        # після цього нові висловлювання вже не з'являться, і drain є детермінованим
        self.vad_flush.set()
        if self._vad_worker is not None:
            self._vad_worker.join(timeout=10.0)
        while not self.stop_event.is_set():
            if self._idle():
                time.sleep(1.0)
                if self._idle():
                    break
            time.sleep(0.5)
        self.file_done.set()

    # ---------- керування ----------

    def pause(self) -> None:
        if not self.running or self.paused:
            return
        self.paused = True
        self.capture_stop.set()  # захоплення зупиняється; VAD дочитує чергу
        self.vad_flush.set()  # закрити поточне висловлювання
        if self.asr_worker is not None:
            self.asr_worker.reset_context()
        self.bus.status.emit("⏸ Пауза")

    def resume(self) -> None:
        if not self.running or not self.paused:
            return
        self.paused = False
        # дочекатися, поки старий VAD-потік зіллє залишки і вийде
        if self._vad_worker is not None and self._vad_worker.is_alive():
            self._vad_worker.join(timeout=2.0)
        self.capture_stop.clear()
        self.vad_flush.clear()
        self._start_capture_and_vad(self.current_device)
        self.bus.status.emit("▶ Слухаю")

    def switch_device(self, device_id: str) -> None:
        """Змінити пристрій без перезапуску ASR/перекладу."""
        self.current_device = device_id
        self.capture_stop.set()  # старий потік захоплення завершується
        self.capture_stop = threading.Event()
        if not self.paused:
            self._start_capture_and_vad(device_id)

    def restart(self) -> None:
        """Повний перезапуск (після зміни моделі/потоків у налаштуваннях)."""
        self.stop()
        self.start(self.current_device)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        self.capture_stop.set()
        self.vad_flush.set()
        for t in self._threads:
            if t is not threading.current_thread() and t.is_alive():
                t.join(timeout=5.0)
        self._threads.clear()
        self._capture = None
        self._vad_worker = None
        self.paused = False
        self.bus.status.emit("⏹ Зупинено")
