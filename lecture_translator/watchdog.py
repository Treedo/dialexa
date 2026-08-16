"""Watchdog: стежить за чергами й затримками, підказує користувачу, а не падає."""
from __future__ import annotations

import logging
import threading
import time

import psutil

log = logging.getLogger(__name__)

INTERVAL = 5.0
_REPEAT_AFTER = 600.0  # не повторювати ту саму підказку 10 хвилин


class Watchdog(threading.Thread):
    def __init__(self, bus, asr_worker, mt_worker, asr_queue, stop_event: threading.Event):
        super().__init__(daemon=True, name="watchdog")
        self.bus = bus
        self.asr_worker = asr_worker
        self.mt_worker = mt_worker
        self.asr_queue = asr_queue
        self.stop_event = stop_event
        self._suggested: dict[str, float] = {}

    def _suggest(self, key: str, text: str) -> None:
        now = time.monotonic()
        if now - self._suggested.get(key, 0) < _REPEAT_AFTER:
            return
        self._suggested[key] = now
        self.bus.watchdog.emit(text)

    def run(self) -> None:
        busy_since = None
        while not self.stop_event.wait(INTERVAL):
            try:
                busy = self.asr_worker.busy_window.fraction()
                depth = self.asr_queue.qsize()
                p90_mt = self.mt_worker.p90_latency()
                rss_gb = psutil.Process().memory_info().rss / 1e9
            except Exception:  # noqa: BLE001
                continue

            if busy > 0.85:
                if busy_since is None:
                    busy_since = time.monotonic()
                if time.monotonic() - busy_since > 60:
                    self._suggest(
                        "asr-busy",
                        "⚠️ Розпізнавання відстає. Спробуйте меншу модель (base) "
                        "або зменшіть навантаження в налаштуваннях.",
                    )
            else:
                busy_since = None

            if p90_mt > 6.0:
                self._suggest(
                    "mt-slow",
                    "⚠️ Переклад повільний. Спробуйте beam_size=1 у налаштуваннях.",
                )

            if depth >= 4:
                self._suggest(
                    "asr-queue-full",
                    "⚠️ Черга розпізнавання переповнена — старі фрази пропускаються.",
                )

            if rss_gb > 3.5:
                self._suggest(
                    "ram",
                    "⚠️ Багато пам'яті: розгляньте меншу модель ASR (base).",
                )
