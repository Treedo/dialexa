"""Потік перекладу: NLLB-600M int8 (CTranslate2) пореченнєво, deu_Latn → ukr_Cyrl.

Кожне речення перекладається окремо і одразу випромінюється в UI —
перші речення висловлювання з'являються, поки решта ще перекладається.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

from .sentence_splitter import split_german

log = logging.getLogger(__name__)


class TranslationWorker(threading.Thread):
    def __init__(
        self,
        mt_queue,
        bus,
        settings,
        model_manager,  # ModelManager (шляхи/готовність моделей)
        ready_event: threading.Event,
        stop_event: threading.Event,
        on_translated=None,  # опц. колбек (utt_id, t_first_ukr) для статистики
    ):
        super().__init__(daemon=True, name="translate")
        self.mt_queue = mt_queue
        self.bus = bus
        self.settings = settings
        self.model_manager = model_manager
        self.ready_event = ready_event
        self.stop_event = stop_event
        self.on_translated = on_translated
        self.sentence_latencies: deque[float] = deque(maxlen=200)
        self._translator = None
        self._sp = None
        self._active = 0
        self._active_lock = threading.Lock()

    def active_count(self) -> int:
        """Скільки висловлювань зараз у перекладі (для очікування завершення)."""
        with self._active_lock:
            return self._active

    def run(self) -> None:
        if os.name != "nt":  # віддаємо процесор ASR на macOS/Linux
            try:
                os.nice(10)
            except Exception:  # noqa: BLE001
                pass
        self.ready_event.wait()
        if self.stop_event.is_set():
            return
        if not self._load():
            return
        self.bus.status.emit("✅ Переклад готовий")

        while not self.stop_event.is_set():
            try:
                utt_id, text = self.mt_queue.get(timeout=0.5)
            except Exception:  # queue.Empty
                continue
            with self._active_lock:
                self._active += 1
            emitted_first = False
            try:
                for idx, sent in enumerate(split_german(text)):
                    try:
                        t0 = time.perf_counter()
                        ukr = self._translate(sent)
                        self.sentence_latencies.append(time.perf_counter() - t0)
                    except Exception as e:  # noqa: BLE001
                        log.exception("translate failed")
                        self.bus.status.emit(f"Помилка перекладу: {e}")
                        continue
                    self.bus.sentence_translated.emit(utt_id, idx, ukr)
                    if not emitted_first and self.on_translated is not None:
                        self.on_translated(utt_id, time.time())
                        emitted_first = True
            finally:
                with self._active_lock:
                    self._active -= 1

    # --- завантаження моделі ---

    def _load(self) -> bool:
        try:
            if self.settings.translation_engine == "nllb":
                return self._load_nllb()
            return self._load_opus()
        except Exception as e:  # noqa: BLE001
            log.exception("translation model load failed")
            self.bus.status.emit(f"Помилка завантаження моделі перекладу: {e}")
            return False

    def _load_nllb(self) -> bool:
        import ctranslate2
        import sentencepiece as spm

        d = self.model_manager.nllb_dir()
        if not self.model_manager.nllb_ready():
            self.bus.status.emit(
                "Модель перекладу відсутня (завантаження не завершилося або скасовано)"
            )
            return False
        self._translator = ctranslate2.Translator(
            str(d),
            device="cpu",
            compute_type="int8",
            inter_threads=1,
            intra_threads=self.settings.translation_intra_threads,
        )
        sp_path = next(d.glob("*.model"), None) or (d / "sentencepiece.bpe.model")
        self._sp = spm.SentencePieceProcessor(model_file=str(sp_path))
        return True

    def _load_opus(self) -> bool:
        import ctranslate2
        import sentencepiece as spm

        d = self.model_manager.opus_dir()
        if not self.model_manager.opus_ready():
            self.bus.status.emit(
                "opus-модель не знайдена: виконайте tools/convert_opus.py "
                "(див. README) або поверніть рушій NLLB у налаштуваннях"
            )
            return False
        self._translator = ctranslate2.Translator(
            str(d), device="cpu", compute_type="int8", inter_threads=1,
            intra_threads=self.settings.translation_intra_threads,
        )
        sp_path = next(d.glob("*.model"), None)
        self._sp = spm.SentencePieceProcessor(model_file=str(sp_path))
        self._opus_src_prefix: list[str] = []
        self._opus_tgt_prefix: list[str] = []
        return True

    # --- власне переклад ---

    def _translate(self, text: str) -> str:
        if self.settings.translation_engine == "nllb":
            return self._translate_nllb(text)
        return self._translate_opus(text)

    def _translate_nllb(self, text: str) -> str:
        pieces = self._sp.encode_as_pieces(text)
        src = [["deu_Latn"] + pieces + ["</s>"]]
        res = self._translator.translate_batch(
            src,
            batch_type="tokens",
            max_batch_size=8,
            beam_size=self.settings.translation_beam_size,
            target_prefix=[["ukr_Cyrl"]],
        )
        out = self._sp.decode(res[0].hypotheses[0])
        # декодер іноді повертає цільовий префікс у тексті гіпотези — прибираємо,
        # у UI лишається лише символ ▶
        if out.startswith("ukr_Cyrl"):
            out = out[len("ukr_Cyrl") :].strip()
        return out

    def _translate_opus(self, text: str) -> str:
        # CTranslate2 приймає рядки напряму і токенізує сам (BPE/SentencePiece моделі)
        res = self._translator.translate_batch(
            [text],
            beam_size=self.settings.translation_beam_size,
        )
        return res[0].hypotheses[0]

    def p90_latency(self) -> float:
        """p90 часу перекладу речення за останні N речень (сек)."""
        if not self.sentence_latencies:
            return 0.0
        s = sorted(self.sentence_latencies)
        return s[int(len(s) * 0.9) - 1 if len(s) >= 10 else -1]
