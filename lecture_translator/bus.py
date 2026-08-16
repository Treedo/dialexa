"""Bus — єдиний канал «робочі потоки → UI».

QObject, що живе в головному (Qt) потоці. Робочі потоки ТІЛЬКИ випромінюють
сигнали на нього — Qt сам доставить їх у головний потік (queued connection).
Жоден воркер ніколи не торкається віджетів напряму.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Bus(QObject):
    # utterance_id, німецький текст (ціле висловлювання)
    german_utterance = Signal(int, str)

    # utterance_id, індекс речення (0-based), український переклад
    sentence_translated = Signal(int, int, str)

    # статусбар
    status = Signal(str)

    # рівень вхідного сигналу 0..1 (для індикатора)
    level = Signal(float)

    # стан VAD: 0 = тиша, 1 = мова (дебаг)
    vad_state = Signal(int)

    # загальний лічильник пропущених висловлювань (drop-oldest)
    skipped = Signal(int)

    # підказка watchdog (банер у статусбарі)
    watchdog = Signal(str)

    # прогрес завантаження моделі: назва, готово (байт), всього (байт, -1 = невідомо)
    download_progress = Signal(str, int, int)

    # завершення завантаження моделі: назва, успіх, повідомлення
    download_done = Signal(str, bool, str)

    # True — вхідного звуку немає 5+ секунд
    silence_detected = Signal(bool)
