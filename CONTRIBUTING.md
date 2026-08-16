# Contributing to Dialexa (Lecture Translator)

Дякуємо за інтерес до проєкту! / Thanks for your interest in the project! 🇺🇦

Dialexa is a desktop app that live-translates German lectures into Ukrainian,
running 100% locally. Contributions of any size are welcome — bug reports,
translations, docs, and code.

## Getting started

```bash
git clone https://github.com/Treedo/dialexa.git
cd lecture-translator
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"   # Windows: .venv\Scripts\pip install -e ".[dev]"
```

Run the app:

```bash
python run.py
```

On first run the app downloads the models (~1.7 GB, one time) — see
[README.md](README.md) for details.

## Running tests

```bash
.venv/bin/python -m pytest
```

- Unit tests (`test_segmenter.py`, `test_sentence_splitter.py`) run without models.
- The integration test (`test_pipeline.py`) is skipped automatically unless the
  models are downloaded and `tests/fixtures/german.wav` exists (generate it on
  macOS with `say -v Anna "..." -o tests/fixtures/german.wav`).

Please run the full suite locally before opening a PR.

## Code style

- Python ≥ 3.11, typed with modern `|` syntax and `from __future__ import annotations`.
- Comments and docstrings are in Ukrainian — the project's original language.
  **Keep them in Ukrainian**, including new code you add.
- Follow the existing structure: worker threads communicate with the UI only
  through the Qt-signal `Bus` (`lecture_translator/bus.py`).
- Keep module-level imports light; heavy libraries (faster-whisper, ctranslate2,
  av, onnxruntime) are imported lazily inside workers.

## Architecture in 60 seconds

```
[system audio] -> vad_q -> [Silero VAD] -> asr_q -> [faster-whisper] -> mt_q -> [NLLB] -> UI
```

- `vad_q` — blocking queue (backpressure), `asr_q`/`mt_q` — drop-oldest queues (4)
  so lag is absorbed by skipping stale utterances, not by accumulating delay.
- `pipeline.py` owns thread lifecycle; workers live in `asr/`, `vad/`,
  `translate/`, `audio/`.
- Models are downloaded on first run into the OS config dir (see `models.py`).

## How to propose changes

1. Open an issue first for anything beyond a trivial fix — describe the problem
   or the idea (English, Ukrainian, or German all fine).
2. Create a branch and make focused commits.
3. Open a PR with a clear description of what and why.
4. CI runs the test suite automatically on every PR.

## Reporting bugs

Include:

- OS + version (macOS/Windows), Python version
- App version and selected models (tiny/base/small, nllb/opus)
- What you expected vs. what happened
- The console output (the app logs to the terminal with `--log`-style INFO lines)

## Code of conduct

Be kind and patient. We want this to be a welcoming place, especially for
first-time contributors and students.
