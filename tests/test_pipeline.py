"""Інтеграційний тест пайплайну з WAV-файлу.

Пропускається, якщо немає моделей або тестового файлу (tests/fixtures/german.wav).
Файл-фікстуру можна згенерувати на macOS: say -v Anna "..." -o tests/fixtures/german.wav
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from lecture_translator.bus import Bus
from lecture_translator.config import Settings, models_dir
from lecture_translator.pipeline import Pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "german.wav"


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


@pytest.fixture(scope="module")
def bus():
    return Bus()


def _models_present() -> bool:
    m = models_dir()
    return (m / "whisper-tiny" / "model.bin").exists() and (
        m / "nllb-600m-int8" / "model.bin"
    ).exists()


def test_pipeline_end_to_end(qapp, bus):
    if not FIXTURE.exists():
        pytest.skip("немає fixtures/german.wav — згенеруйте через `say -v Anna`")
    if not _models_present():
        pytest.skip("моделі не завантажені — запустіть застосунок один раз")

    settings = Settings()
    settings.asr_model = "tiny"
    pipeline = Pipeline(bus, settings)

    german: list[str] = []
    ukrainian: list[str] = []
    bus.german_utterance.connect(lambda _id, text: german.append(text))
    bus.sentence_translated.connect(lambda _id, _idx, text: ukrainian.append(text))

    pipeline.start_file(str(FIXTURE), speed=0)
    deadline = time.time() + 180
    while not pipeline.file_done.is_set() and time.time() < deadline:
        qapp.processEvents()  # доставка queued-сигналів bus у цьому потоці
        time.sleep(0.5)
    # доставити останні queued-сигнали (німецький текст + переклади)
    for _ in range(8):
        qapp.processEvents()
        time.sleep(0.1)
    pipeline.stop()

    assert pipeline.file_done.is_set(), "пайплайн не завершився за 180 с"
    assert german, "не розпізнано жодного висловлювання"
    assert ukrainian, "не отримано жодного перекладу"
    assert all(t.strip() for t in ukrainian), "порожній переклад"
