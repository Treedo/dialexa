"""Потоковий ресемплінг довільної частоти -> 16 кГц моно float32 (libsamplerate)."""
from __future__ import annotations

import numpy as np

TARGET_RATE = 16000


class StreamingResampler:
    """Ресемплер зі збереженням стану між викликами.

    libsamplerate сам тримає внутрішній стан, тому межі між блоками точні
    навіть для некратних частот (44100 / 16000 = 2.75625).
    """

    def __init__(self, in_rate: int, out_rate: int = TARGET_RATE):
        import samplerate  # лінивий імпорт: важка бібліотека потрібна лише в потоці аудіо

        self.in_rate = int(in_rate)
        self.out_rate = out_rate
        ratio = out_rate / self.in_rate
        self._rs = samplerate.Resampler("sinc_medium", channels=1)
        self._ratio = ratio

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """chunk: float32 моно довільної довжини; повертає float32 16 кГц (можливо, порожній)."""
        if chunk.size == 0:
            return np.empty(0, dtype=np.float32)
        return self._rs.process(chunk.astype(np.float32, copy=False), self._ratio)

    def flush(self) -> np.ndarray:
        """Дописати залишки внутрішнього буфера (наприкінці потоку)."""
        try:
            return self._rs.process(np.empty(0, dtype=np.float32), self._ratio, end_of_input=True)
        except TypeError:  # старіші версії samplerate без end_of_input
            return np.empty(0, dtype=np.float32)
