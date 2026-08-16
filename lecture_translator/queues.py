"""Черги пайплайну: DropOldestQueue (політика drop-oldest) та RingBuffer (для дебагу)."""
from __future__ import annotations

import queue
import threading
from collections import deque

import numpy as np


class DropOldestQueue:
    """Черга фіксованої глибини: новий елемент витісняє найстаріший.

    Використовується там, де відставання неприпустиме (ASR і переклад):
    краще пропустити старе висловлювання, ніж накопичувати хвилини затримки.
    """

    def __init__(self, maxsize: int):
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self.dropped = 0

    def put(self, item) -> None:
        while True:
            try:
                self._q.put_nowait(item)
                return
            except queue.Full:
                try:
                    self._q.get_nowait()
                    self.dropped += 1
                except queue.Empty:
                    continue

    def get(self, timeout: float | None = None):
        return self._q.get(timeout=timeout)

    def qsize(self) -> int:
        return self._q.qsize()


class RingBuffer:
    """Останні N секунд аудіо (для осцилограми в UI). Потокобезпечний."""

    def __init__(self, seconds: float = 3.0, rate: int = 16000):
        self.maxlen = int(seconds * rate)
        self._chunks: deque[np.ndarray] = deque()
        self._total = 0
        self._lock = threading.Lock()

    def append(self, chunk: np.ndarray) -> None:
        with self._lock:
            self._chunks.append(chunk)
            self._total += chunk.size
            while self._total > self.maxlen and self._chunks:
                self._total -= self._chunks.popleft().size

    def snapshot(self) -> np.ndarray:
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(list(self._chunks))

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._total = 0
