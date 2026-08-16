"""Стейт-машина розрізання потоку на висловлювання за ймовірностями VAD.

Чиста логіка без Qt/soundcard/onnx — тестується синтетичними масивами.
Вхід: вікна по 512 семплів @ 16 кГц (32 мс) + ймовірність мови для кожного.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

import numpy as np

from .vad_model import WINDOW_SAMPLES

SAMPLE_RATE = 16000
WINDOW_MS = WINDOW_SAMPLES / SAMPLE_RATE * 1000  # 32 мс


@dataclass
class Utterance:
    id: int
    audio: np.ndarray  # float32, 16 кГц, моно
    t_end: float  # wall-clock часу завершення (для заміру затримки)


class Segmenter:
    def __init__(
        self,
        *,
        threshold: float = 0.5,
        min_speech_ms: int = 300,
        silence_ms: int = 600,
        pad_ms: int = 300,
        max_utterance_ms: int = 10000,
    ):
        self.threshold = threshold
        self.min_speech_windows = max(1, round(min_speech_ms / WINDOW_MS))
        self.silence_windows = max(1, round(silence_ms / WINDOW_MS))
        self.pad_windows = max(0, round(pad_ms / WINDOW_MS))
        self.max_utterance_windows = max(1, round(max_utterance_ms / WINDOW_MS))
        self._reset()

    def _reset(self) -> None:
        self._speech = False
        self._buf: list[np.ndarray] = []
        self._pre: deque[np.ndarray] = deque(maxlen=self.pad_windows)
        self._silent = 0
        self._speech_windows = 0
        self._next_id = 1

    def process(self, window: np.ndarray, speech_prob: float) -> list[Utterance]:
        """Подає одне вікно (512 семплів); повертає завершені висловлювання (0 або 1)."""
        out: list[Utterance] = []
        is_speech = speech_prob >= self.threshold

        if not self._speech:
            if is_speech:
                self._speech = True
                self._buf = list(self._pre)  # пре-рол перед початком мови
                self._pre.clear()
                self._buf.append(window)  # поточне вікно завжди входить
                self._silent = 0
                self._speech_windows = 1
            else:
                self._pre.append(window)
            return out

        # мова триває
        self._buf.append(window)
        if is_speech:
            self._speech_windows += 1
            self._silent = 0
        else:
            self._silent += 1  # пад-хвіст вже додано у _buf

        if self._silent >= self.silence_windows or len(self._buf) >= self.max_utterance_windows:
            utt = self._close()
            if utt is not None:
                out.append(utt)
        return out

    def flush(self) -> list[Utterance]:
        """Закрити незавершене висловлювання (наприкінці потоку / при паузі)."""
        out: list[Utterance] = []
        if self._speech:
            utt = self._close()
            if utt is not None:
                out.append(utt)
        return out

    def reset(self) -> None:
        """Очистити стан (після паузи); лічильник id НЕ скидається."""
        self._speech = False
        self._buf = []
        self._pre.clear()
        self._silent = 0
        self._speech_windows = 0

    def _close(self) -> Utterance | None:
        self._speech = False
        windows = self._buf
        self._buf = []
        self._silent = 0
        if self._speech_windows < self.min_speech_windows:
            self._speech_windows = 0
            return None  # надто коротка мова (без хвоста тиші) — відкидаємо
        self._speech_windows = 0
        utt = Utterance(id=self._next_id, audio=np.concatenate(windows), t_end=time.time())
        self._next_id += 1
        return utt
