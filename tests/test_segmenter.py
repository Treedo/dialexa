import numpy as np

from lecture_translator.vad.segmenter import Segmenter


def _speech_window():
    return np.random.default_rng(42).standard_normal(512).astype(np.float32)


def _silence_window():
    return np.zeros(512, dtype=np.float32)


def test_basic_utterance_with_tail_silence():
    seg = Segmenter(threshold=0.5, min_speech_ms=300, silence_ms=600, pad_ms=0)
    out = []
    for _ in range(20):  # 640 мс мови
        out += seg.process(_speech_window(), 1.0)
    assert out == []  # ще не закрито
    for _ in range(20):  # 640 мс тиші
        out += seg.process(_silence_window(), 0.0)
    assert len(out) == 1
    # 20 вікон мови + 19 вікон тиші (хвіст = silence_windows, входить у висловлювання)
    assert out[0].audio.size == 39 * 512


def test_too_short_utterance_discarded():
    seg = Segmenter(min_speech_ms=300, silence_ms=600, pad_ms=0)
    out = []
    for _ in range(3):  # 96 мс — менше за мінімум
        out += seg.process(_speech_window(), 1.0)
    for _ in range(20):
        out += seg.process(_silence_window(), 0.0)
    assert out == []


def test_preroll_included():
    seg = Segmenter(min_speech_ms=300, silence_ms=600, pad_ms=300, max_utterance_ms=10000)
    out = []
    for _ in range(9):  # пре-рол: 288 мс тиші
        out += seg.process(_silence_window(), 0.0)
    assert out == []
    for _ in range(10):
        out += seg.process(_speech_window(), 1.0)
    for _ in range(20):
        out += seg.process(_silence_window(), 0.0)
    assert len(out) == 1
    # 9 вікон пре-ролу + 10 вікон мови + 19 вікон хвоста тиші
    assert out[0].audio.size == (9 + 10 + 19) * 512


def test_max_utterance_force_split():
    seg = Segmenter(min_speech_ms=300, silence_ms=600, pad_ms=0, max_utterance_ms=320)
    out = []
    for _ in range(12):  # безперервна мова 384 мс > 320 мс максимум
        out += seg.process(_speech_window(), 1.0)
    assert len(out) == 1
    assert out[0].audio.size == 10 * 512  # розрізано на 10-му вікні


def test_flush_closes_partial():
    seg = Segmenter(min_speech_ms=300, silence_ms=600, pad_ms=0)
    for _ in range(10):
        seg.process(_speech_window(), 1.0)
    out = seg.flush()
    assert len(out) == 1
    assert seg.flush() == []  # повторний flush порожній


def test_reset_keeps_utterance_ids():
    seg = Segmenter(min_speech_ms=300, silence_ms=600, pad_ms=0)
    for _ in range(10):
        seg.process(_speech_window(), 1.0)
    first = seg.flush()[0]
    seg.reset()
    for _ in range(10):
        seg.process(_speech_window(), 1.0)
    second = seg.flush()[0]
    assert second.id == first.id + 1
