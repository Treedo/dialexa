"""Захоплення системного звуку.

macOS: читає вхідний пристрій «BlackHole 2ch» (віртуальний драйвер; системний
звук маршрутизується в нього через Multi-Output Device в Audio MIDI Setup).
Windows: WASAPI loopback-пристрій потрібного виходу (без жодних драйверів).
"""
from __future__ import annotations

import logging
import platform
import threading
import time

import numpy as np
import soundcard as sc

from ..audio.resample import StreamingResampler, TARGET_RATE
from ..queues import RingBuffer

log = logging.getLogger(__name__)

BLOCKSIZE = 1024  # ~21 мс при 48 кГц
_TRIED_RATES = (48000, 44100)  # BlackHole та WASAPI стандартно працюють на цих частотах


def list_input_devices() -> list[dict]:
    """Усі вхідні пристрої: {id, name, loopback}.

    macOS: звичайні входи CoreAudio (включно з BlackHole, якщо встановлено).
    Windows: мікрофони + loopback-пристрої виходів (позначені [Loopback]).
    """
    out = []
    # loopback підтримується soundcard лише на Windows (WASAPI); на macOS
    # його роль виконує BlackHole як звичайний вхідний пристрій.
    include_loopback = platform.system() == "Windows"
    try:
        mics = sc.all_microphones(include_loopback=include_loopback)
    except TypeError:  # старіша версія soundcard без loopback
        mics = sc.all_microphones()
    for m in mics:
        out.append(
            {
                "id": str(m.id),
                "name": str(m.name),
                "loopback": "loopback" in str(m.name).lower(),
            }
        )
    return out


def find_blackhole(devices: list[dict]) -> str | None:
    for d in devices:
        if "blackhole" in d["name"].lower():
            return d["name"]
    return None


def find_default_loopback(devices: list[dict]) -> str | None:
    for d in devices:
        if d["loopback"]:
            return d["name"]
    return None


def resolve_device(configured: str | None, devices: list[dict] | None = None) -> str | None:
    """Придатний до відкриття пристрій — за іменем, а не за id.

    soundcard на macOS зіставляє пристрої за числовим CoreAudio id (int), а ми
    зберігаємо рядки, тому id марний; до того ж CoreAudio id змінюються між
    перезавантаженнями. Порядок: явно обране ім'я (якщо існує) -> BlackHole
    (macOS) -> loopback (Windows) -> системний мікрофон.
    """
    devices = list_input_devices() if devices is None else devices
    names = {d["name"] for d in devices}
    if configured and configured in names:
        return configured
    if configured and configured.isdigit():
        pass  # застарілий CoreAudio id зі старого конфіга — обираємо за замовчуванням
    bh = find_blackhole(devices)
    if bh:
        return bh
    lb = find_default_loopback(devices)
    if lb:
        return lb
    try:
        return str(sc.default_microphone().name)
    except Exception:  # noqa: BLE001
        return None


def _open_recorder(device_id: str | None):
    """Відкриває soundcard-recorder на пристрої; повертає (name, recorder, wrapper, rate).

    device_id — ім'я пристрою (з конфіга/діалога) або None для автовибіру.

    soundcard вимагає, щоб recorder відкривали через контекстний менеджер
    (__enter__ створює платформний _Recorder з чергою блоків). Частоту пробуємо
    48 кГц → 44.1 кГц; після відкриття потік працює на запитуваній частоті.
    """
    name = resolve_device(device_id)
    if not name:
        raise RuntimeError("Не знайдено жодного вхідного аудіопристрою")
    mic = sc.get_microphone(name)
    last_err: Exception | None = None
    for rate in _TRIED_RATES:
        try:
            wrapper = mic.recorder(samplerate=rate)
            rec = wrapper.__enter__()
            return str(mic.name), rec, wrapper, int(rate)
        except Exception as e:  # noqa: BLE001 - перебираємо частоти, потім здаємося
            last_err = e
            time.sleep(0.5)
    raise RuntimeError(f"Не вдалося відкрити пристрій «{mic.name}»: {last_err}")


class AudioCapture(threading.Thread):
    """Потік читання: пристрій -> моно -> 16 кГц -> VAD-черга + ring buffer.

    Якщо vad_queue is None — «пробний» режим (для тесту рівня в діалозі
    пристрою): нічого не накопичуємо, лише випромінюємо рівень сигналу.
    """

    def __init__(
        self,
        bus,
        device_id: str | None = None,
        vad_queue=None,
        ring: RingBuffer | None = None,
        stop_event: threading.Event | None = None,
    ):
        super().__init__(daemon=True, name="audio-capture")
        self.bus = bus
        self.device_id = device_id
        self.vad_queue = vad_queue
        self.ring = ring
        self.stop_event = stop_event or threading.Event()
        self._last_level_time = 0.0

    def run(self) -> None:
        try:
            name, rec, wrapper, rate = _open_recorder(self.device_id)
        except Exception as e:  # noqa: BLE001
            log.exception("audio capture open failed")
            self.bus.status.emit(f"Не вдалося відкрити пристрій: {e}")
            # жовта підказка лишається видимою, навіть коли пізніше
            # завантажувач моделей затирає рядок статусу «Готово»
            self.bus.watchdog.emit(
                "🎧 Не вдалося відкрити аудіопристрій — оберіть «Джерело звуку» в тулбарі"
            )
            return
        resampler = StreamingResampler(rate)
        self.bus.status.emit(f"🎧 Слухаю: {name}")
        block_i = 0
        last_sound = time.monotonic()
        silence_warned = False
        while not self.stop_event.is_set():
            try:
                data = rec.record(numframes=BLOCKSIZE)  # (blocksize, channels) float32
            except Exception as e:  # noqa: BLE001
                log.warning("record error: %s", e)
                time.sleep(0.5)
                continue
            mono = data.mean(axis=1) if data.ndim > 1 else data
            rms = float(np.sqrt(np.mean(np.square(mono))))
            if rms > 0.003:
                last_sound = time.monotonic()
            now = time.monotonic()
            if now - last_sound > 5.0 and not silence_warned:
                silence_warned = True
                self.bus.silence_detected.emit(True)
            elif now - last_sound <= 5.0 and silence_warned:
                silence_warned = False
                self.bus.silence_detected.emit(False)
            out = resampler.process(mono)
            if out.size:
                if self.ring is not None:
                    self.ring.append(out)
                if self.vad_queue is not None:
                    self.vad_queue.put(out)  # блокуюча черга = backpressure
            # індикатор рівня ~5 разів на секунду
            block_i += 1
            if block_i % 9 == 0:
                if now - self._last_level_time >= 0.18:
                    self._last_level_time = now
                    self.bus.level.emit(min(1.0, rms * 4.0))
        try:
            wrapper.__exit__(None, None, None)  # закриває платформний recorder
        except Exception:  # noqa: BLE001
            pass
