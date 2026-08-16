"""Налаштування застосунку: dataclass + атомарний JSON у каталозі конфігів ОС."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from platformdirs import user_config_dir


@dataclass
class Settings:
    # --- аудіо ---
    audio_device: str = ""  # "" = автовибір (BlackHole на macOS / loopback на Windows)

    # --- розпізнавання (ASR) ---
    asr_model: str = "small"  # tiny | base | small
    asr_beam_size: int = 1
    asr_cpu_threads: int = 6
    asr_previous_text_max_chars: int = 1500

    # --- переклад ---
    translation_engine: str = "nllb"  # nllb | opus (opus потребує конвертованої моделі)
    translation_beam_size: int = 4
    translation_intra_threads: int = 4

    # --- VAD (мс) ---
    vad_threshold: float = 0.5
    vad_silence_ms: int = 600
    vad_min_speech_ms: int = 300
    vad_max_utterance_ms: int = 10000
    vad_pad_ms: int = 300

    # --- інтерфейс ---
    ui_font_size: int = 13
    ui_dark_mode: bool = True

    save_dir: str = ""
    first_run_done: bool = False

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_path()
        s = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                for k, v in data.items():
                    if k in known:
                        setattr(s, k, v)
            except (json.JSONDecodeError, OSError):
                pass  # пошкоджений конфіг -> дефолти
        else:
            s._adapt_threads_to_cpu()
        # застарілі числові CoreAudio id (macOS): soundcard не може їх знайти,
        # а самі id змінюються між перезавантаженнями -> автовибір за іменем
        if isinstance(s.audio_device, int) or (
            isinstance(s.audio_device, str) and s.audio_device.isdigit()
        ):
            s.audio_device = ""
        if not s.save_dir:
            s.save_dir = str(Path.home() / "Documents" / "lecture-translator-sessions")
        return s

    def _adapt_threads_to_cpu(self) -> None:
        """Перший запуск: підлаштувати потоки ASR/перекладу під кількість ядер.

        Забагато потоків на малому CPU дає перепідписку і 3-5× уповільнення.
        """
        cores = os.cpu_count() or 4
        self.asr_cpu_threads = max(2, min(8, cores - 2))
        self.translation_intra_threads = max(1, min(4, cores - 2))

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)


def config_path() -> Path:
    """Шлях до config.json: ~/Library/Application Support/lecture-translator (macOS),
    %LOCALAPPDATA%\\lecture-translator (Windows)."""
    return Path(user_config_dir("lecture-translator")) / "config.json"


def models_dir() -> Path:
    """Каталог, куди завантажуються моделі (~1.7 ГБ)."""
    return Path(user_config_dir("lecture-translator")) / "models"
