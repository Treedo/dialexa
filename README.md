<div align="center">

# 🎓 Dialexa — Lecture Translator

**Live German → Ukrainian lecture translation, fully on your device.**

Real-time bilingual transcript of German lectures: the original German
(grey, smaller) with an instant Ukrainian translation underneath.

*No cloud. No API keys. Your lecture audio never leaves your computer.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/Treedo/dialexa/actions/workflows/ci.yml/badge.svg)](https://github.com/Treedo/dialexa/actions/workflows/ci.yml)
[![Platform: macOS](https://img.shields.io/badge/macOS-%F0%9F%8D%8E-silver.svg)]()
[![Platform: Windows](https://img.shields.io/badge/Windows-%F0%9F%AA%9F-blue.svg)]()

</div>

<!-- Add a screenshot once you have one:
![Dialexa UI](docs/screenshot.png)
-->

## What it does

Dialexa listens to the **system audio** of your online lecture (Zoom, Teams,
Moodle, YouTube) and shows a live bilingual feed in a small desktop window:

- 🎧 speech activity detection (VAD) segments the audio stream
- ✍️ a German speech recognizer transcribes each utterance
- 🌐 each sentence is translated to Ukrainian as soon as it is recognized
- 💾 everything can be saved as a timestamped bilingual `.md` summary

Typical latency: **2–5 seconds** from speech to Ukrainian text on screen.
Memory footprint: ~2 GB. Runs on Intel MacBook 2019+ and Windows.

## How it works

```
[system audio] ──► vad_q ──► [Silero VAD] ──► asr_q ──► [faster-whisper] ──► mt_q ──► [NLLB] ──► UI
                                                      │                                          ▲
                                                      └──► German utterance ────────────────────┘
```

| Component | Technology |
|---|---|
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (`small` int8, German; tiny/base/small selectable) |
| Voice activity detection | [Silero VAD](https://github.com/snakers4/silero-vad) (ONNX runtime, no torch, ~2 MB) |
| Translation | NLLB-200 distilled 600M int8 (CTranslate2), `deu_Latn → ukr_Cyrl` |
| Audio capture | macOS: [BlackHole](https://existential.audio/blackhole/) driver · Windows: WASAPI loopback (no drivers) |
| UI | PySide6 (Qt 6) |

All models run locally — the internet is needed only once, to download them
(~1.7 GB total, resumable).

## Installation

### Ready-to-use build (no Python needed)

Prebuilt apps are attached to [GitHub Releases](https://github.com/Treedo/dialexa/releases):

- **macOS 12+ (Intel)** — `Dialexa-<version>-macos-x86_64.zip`
  (runs on Apple Silicon via Rosetta; a native arm64 build is planned)
- Windows build — coming soon

To install on macOS: download the zip, unpack it, move `Dialexa.app` to
`/Applications`, and open it. Because the bundle is ad-hoc signed, the first
launch is **right-click → Open** (or `xattr -cr Dialexa.app` in the terminal).

> ⚠️ The BlackHole driver is still required on macOS (see below) — it cannot
> be bundled into the app. Models (~1.7 GB) are downloaded on first launch.

### From source

Requires **Python 3.11+**.

```bash
git clone https://github.com/Treedo/dialexa.git
cd lecture-translator
python3 -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
python run.py
```

On the first run the app downloads the models (~1.7 GB, one time) and walks
you through audio source setup.

## macOS: capture system audio (one-time setup)

macOS does not let apps read system audio without an extra driver:

1. `brew install blackhole-2ch` (or download from existential.audio)
2. Open **Audio MIDI Setup** (Applications → Utilities)
3. Click **+** (bottom left) → **Create Multi-Output Device**
4. Check **BlackHole 2ch** and your speakers/headphones
5. Select the Multi-Output Device as your output (volume menu)
6. In Dialexa, pick **BlackHole 2ch** as the audio source

Notes:

- while a Multi-Output Device is active, the volume keys may not work —
  adjust volume inside the lecture app instead;
- macOS will ask for microphone permission — that is expected
  (BlackHole looks like a microphone).

## Windows

No drivers needed: in the audio source dialog, select the **loopback device**
of the output your lecture plays on.

## Usage

- **⏸ Pause / ▶ Resume** — stop/resume listening
- **🗑 Clear** — clear the transcript feed
- **💾 Save** — save the bilingual notes to a timestamped `.md`
  (default: `~/Documents/lecture-translator-sessions`; auto-saved on exit)
- Every utterance has a 🕐 timestamp (the time it was recognized)
- **🎧 Audio source** — switch devices on the fly (with a live level test)
- **Model** — tiny / base / small (smaller = faster, bigger = more accurate)
- If there is no audio for 5 seconds, the status bar shows a routing hint
- If recognition falls behind, a watchdog suggests a smaller model or `beam_size=1`

## Test mode (no audio device needed)

```bash
python run.py --file lecture.wav --stats      # real-time pace + latency stats
python run.py --file lecture.wav --speed 0    # fast run, no real-time pacing
```

## Optional: faster opus-mt-de-uk engine

NLLB is the recommended engine. If you want to experiment with the faster
(but weaker) opus-mt-de-uk:

```bash
.venv/bin/pip install transformers torch ct2-transformers
.venv/bin/python tools/convert_opus.py
```

then select the **opus** engine in Settings.

## Packaging as a macOS .app ("Dialexa")

So students can launch the app from an icon without Python:

```bash
.venv/bin/pip install -e ".[dev]"
tools/build_macos_app.sh          # → dist/Dialexa.app
```

The script generates the icon, builds a PyInstaller bundle and ad-hoc signs it.
Models are **not** bundled — they are downloaded on first launch into
`~/Library/Application Support/lecture-translator/models` (the same directory
as in dev mode, so nothing is downloaded twice).

Distribution notes:

- the build is architecture-bound: on an Intel Mac you get an x86_64 bundle
  (works on Apple Silicon via Rosetta); build on an M-series Mac for native arm64;
- the bundle is ad-hoc signed, so on another Mac the first launch is
  right-click → **Open** (or `xattr -cr Dialexa.app`); a Developer ID is needed
  for mass distribution;
- students still need to install BlackHole once (see above) — without it
  macOS does not expose system audio.

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

The integration test (`tests/test_pipeline.py`) is skipped unless the models
are downloaded and `tests/fixtures/german.wav` exists (generate it on macOS:
`say -v Anna "..." -o tests/fixtures/german.wav`).

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture notes and guidelines.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Nothing appears in the feed | Make sure the lecture plays into the **Multi-Output Device** (not directly into "BlackHole 2ch") |
| Volume keys don't work | Normal for Multi-Output Device; adjust volume in the lecture app |
| Recognition falls behind | Settings: smaller model (base), ASR `beam_size=1`, fewer translation threads |
| Translation is slow | Settings: translation `beam_size=1` (or the opus engine) |
| Model download error | Restart the app — the download resumes where it left off |
| Queue overflow ("skipped: N") | Close heavy apps or switch to a smaller model |

## License

[MIT](LICENSE) © 2026 treedo

---

## Українською 🇺🇦

**Dialexa (Lecture Translator)** — десктоп-застосунок для студентів, який слухає
системний звук онлайн-лекції німецькою та одразу показує двомовну стрічку:
німецький оригінал + український переклад. Усе працює **повністю локально** —
без хмар і API-ключів; інтернет потрібен лише один раз, щоб завантажити моделі
(~1.7 ГБ).

- Розпізнавання: faster-whisper (німецька), детекція мови: Silero VAD,
  переклад: NLLB-200 600M int8 (`deu → ukr`)
- Затримка зазвичай **2–5 с**, ~2 ГБ пам'яті, працює на Intel MacBook 2019+ і Windows
- macOS: потрібен драйвер **BlackHole** (інструкція вище); Windows — без драйверів (WASAPI loopback)
- Конспект зберігається у `~/Documents/lecture-translator-sessions` з мітками часу

Встановлення: `pip install -e .` та `python run.py` (деталі — у розділі
[Installation](#installation)). Внесок у проєкт вітається — див.
[CONTRIBUTING.md](CONTRIBUTING.md).
