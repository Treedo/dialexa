"""Потік VAD: складає 512-семпл вікна з черги, жене Silero, віддає висловлювання в ASR."""
from __future__ import annotations

import logging
import queue
import threading

import numpy as np

from .segmenter import Segmenter
from .vad_model import SileroVAD, WINDOW_SAMPLES

log = logging.getLogger(__name__)


class VADWorker(threading.Thread):
    def __init__(
        self,
        vad_queue: queue.Queue,
        asr_queue,
        segmenter: Segmenter,
        vad_model: SileroVAD,
        bus,
        stop_event: threading.Event,
        flush_event: threading.Event | None = None,
    ):
        super().__init__(daemon=True, name="vad")
        self.vad_queue = vad_queue
        self.asr_queue = asr_queue
        self.segmenter = segmenter
        self.vad_model = vad_model
        self.bus = bus
        self.stop_event = stop_event
        self.flush_event = flush_event

    def run(self) -> None:
        pending = np.empty(0, dtype=np.float32)
        while not self.stop_event.is_set():
            try:
                chunk = self.vad_queue.get(timeout=0.5)
            except queue.Empty:
                if self._maybe_flush():
                    break
                continue
            if pending.size:
                pending = np.concatenate((pending, chunk))
            else:
                pending = chunk
            while pending.size >= WINDOW_SAMPLES:
                window = pending[:WINDOW_SAMPLES]
                pending = pending[WINDOW_SAMPLES:]
                prob = self.vad_model(window)
                self.bus.vad_state.emit(1 if prob >= self.segmenter.threshold else 0)
                for utt in self.segmenter.process(window, prob):
                    self.asr_queue.put(utt)
        # фінальне злиття на зупинці
        self._flush()

    def _maybe_flush(self) -> bool:
        """Пауза: черга спорожніла — закриваємо незавершене висловлювання і виходимо.

        VAD-потік живе в межах однієї сесії захоплення: при паузі він завершується,
        при resume пайплайн стартує новий (інакше два споживачі однієї черги).
        """
        if self.flush_event is not None and self.flush_event.is_set():
            self._flush()
            return True
        return False

    def _flush(self) -> None:
        for utt in self.segmenter.flush():
            self.asr_queue.put(utt)
        self.segmenter.reset()
