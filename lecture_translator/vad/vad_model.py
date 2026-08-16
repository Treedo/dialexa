"""Silero VAD поверх onnxruntime (без torch — лише ~2 МБ модель).

Модель: silero_vad.onnx (512 семплів @ 16 кГц, з внутрішнім станом h/c).
Файл шукається в кеші моделей; якщо немає — завантажується з GitHub silero-vad.
"""
from __future__ import annotations

import logging
import shutil
import urllib.request
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

SILERO_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
WINDOW_SAMPLES = 512  # 32 мс @ 16 кГц
CONTEXT_SAMPLES = 64  # контекст від попереднього вікна (рецептивне поле моделі)


def _ssl_context() -> "ssl.SSLContext | None":
    """SSL-контекст із системними/пакованими сертифікатами.

    Python.org-збірки на macOS не бачать системних сертифікатів — certifi рятує.
    """
    try:
        import certifi  # входить у залежності huggingface_hub

        import ssl

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return None


def ensure_silero_model(models_dir: Path) -> Path:
    """Повертає шлях до silero_vad.onnx; завантажує при потребі (~1.7 МБ)."""
    dest = models_dir / "silero_vad.onnx"
    if dest.exists() and dest.stat().st_size > 100_000:
        return dest
    models_dir.mkdir(parents=True, exist_ok=True)
    log.info("Завантажую silero_vad.onnx з GitHub...")
    tmp = dest.with_suffix(".onnx.part")
    req = urllib.request.Request(SILERO_URL, headers={"User-Agent": "lecture-translator"})
    with urllib.request.urlopen(req, context=_ssl_context()) as resp, open(tmp, "wb") as f:  # noqa: S310
        shutil.copyfileobj(resp, f)
    tmp.rename(dest)
    return dest


class SileroVAD:
    """Обгортка над silero_vad.onnx: подавайте рівно 512 семплів float32."""

    def __init__(self, model_path: Path):
        import onnxruntime as ort  # лінивий імпорт

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self._sess = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"], sess_options=opts
        )
        self._sr = np.array(16000, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros(CONTEXT_SAMPLES, dtype=np.float32)

    def __call__(self, window: np.ndarray) -> float:
        """window: (512,) float32; повертає ймовірність мови 0..1.

        Потоковий рецепт Silero: на вхід моделі подається 64-семпл контекст
        попереднього вікна + 512 поточних (разом 576); інакше рецептивне поле
        обрізане і ймовірності звалені в нуль.
        """
        ort_inputs = {
            "input": np.concatenate([self._context, window]).reshape(1, -1),
            "state": self._state,
            "sr": self._sr,
        }
        out, self._state = self._sess.run(None, ort_inputs)
        self._context = window[-CONTEXT_SAMPLES:].copy()
        return float(np.asarray(out).reshape(-1)[0])
