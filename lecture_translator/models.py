"""Завантаження моделей з Hugging Face з прогресом у UI та підтримкою скасування.

Моделі:
  - whisper-{tiny,base,small}: Systran/faster-whisper-{size} (CTranslate2 int8)  ~150/290/484 МБ
  - nllb-600m-int8:            mijuanlo/nllb-200-distilled-600M-ct2-int8         ~1.2 ГБ
  - silero_vad.onnx:           ~1.7 МБ (див. vad/vad_model.py)
"""
from __future__ import annotations

import logging
import threading
from functools import partial
from pathlib import Path

from huggingface_hub import snapshot_download
from tqdm import tqdm

from .config import models_dir

log = logging.getLogger(__name__)

WHISPER_REPO = "Systran/faster-whisper-{size}"
NLLB_REPO = "mijuanlo/nllb-200-distilled-600M-ct2-int8"


class DownloadCancelled(Exception):
    pass


class _BusProgress(tqdm):
    """tqdm-адаптер: дублює прогрес у сигнал bus + підтримує скасування."""

    def __init__(self, *args, model_name: str = "", bus=None, cancel_event=None, **kwargs):
        self._bus = bus
        self._name = model_name
        self._cancel = cancel_event
        super().__init__(*args, **kwargs)
        self._emit()

    def update(self, n: float = 1) -> bool | None:
        if self._cancel is not None and self._cancel.is_set():
            raise DownloadCancelled(self._name)
        res = super().update(n)
        self._emit()
        return res

    def _emit(self) -> None:
        if self._bus is not None:
            total = int(self.total) if self.total else -1
            self._bus.download_progress.emit(self._name, int(self.n), total)


class ModelManager:
    def __init__(self, bus, cancel_event: threading.Event | None = None):
        self.bus = bus
        self.cancel_event = cancel_event or threading.Event()

    # --- шляхи та готовність ---

    def whisper_dir(self, size: str) -> Path:
        return models_dir() / f"whisper-{size}"

    def nllb_dir(self) -> Path:
        return models_dir() / "nllb-600m-int8"

    def opus_dir(self) -> Path:
        return models_dir() / "opus-mt-de-uk"

    @staticmethod
    def _ready(d: Path) -> bool:
        return (d / "model.bin").exists()

    def whisper_ready(self, size: str) -> bool:
        return self._ready(self.whisper_dir(size))

    def nllb_ready(self) -> bool:
        return self._ready(self.nllb_dir())

    def opus_ready(self) -> bool:
        return self._ready(self.opus_dir())

    def needed(self, settings) -> list[str]:
        """Назви моделей, які ще треба завантажити (для діалогу прогресу).

        opus-модель не завантажується автоматично (потрібна ручна конвертація) —
        вона сюди не потрапляє, а про її відсутність повідомляє воркер перекладу.
        """
        out = []
        if not self.whisper_ready(settings.asr_model):
            out.append(f"whisper-{settings.asr_model}")
        if settings.translation_engine == "nllb" and not self.nllb_ready():
            out.append("nllb-600m-int8")
        return out

    # --- завантаження ---

    def _snapshot(self, repo_id: str, dest: Path, model_name: str) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        tqdm_cls = partial(
            _BusProgress,
            model_name=model_name,
            bus=self.bus,
            cancel_event=self.cancel_event,
        )
        snapshot_download(
            repo_id,
            local_dir=str(dest),
            tqdm_class=tqdm_cls,
        )

    def ensure_whisper(self, size: str) -> Path:
        dest = self.whisper_dir(size)
        if not self.whisper_ready(size):
            self.bus.download_progress.emit(f"whisper-{size}", 0, -1)
            self._snapshot(WHISPER_REPO.format(size=size), dest, f"whisper-{size}")
            self.bus.download_done.emit(f"whisper-{size}", True, "")
        return dest

    def ensure_nllb(self) -> Path:
        dest = self.nllb_dir()
        if not self.nllb_ready():
            self.bus.download_progress.emit("nllb-600m-int8", 0, -1)
            self._snapshot(NLLB_REPO, dest, "nllb-600m-int8")
            self.bus.download_done.emit("nllb-600m-int8", True, "")
        return dest

    def ensure_all(self, settings, ready_event: threading.Event) -> None:
        """Ціль фонового потоку: завантажує потрібні моделі, потім set(ready_event)."""
        try:
            self.ensure_whisper(settings.asr_model)
            if settings.translation_engine == "nllb":
                self.ensure_nllb()
            # opus: очікуємо вже конвертований каталог (див. tools/convert_opus.py)
        except DownloadCancelled:
            log.info("Завантаження моделей скасовано користувачем")
            self.bus.status.emit("Завантаження моделей скасовано — можна повторити пізніше")
        except Exception as e:  # noqa: BLE001
            log.exception("model download failed")
            self.bus.status.emit(f"Помилка завантаження моделі: {e}")
        finally:
            ready_event.set()
