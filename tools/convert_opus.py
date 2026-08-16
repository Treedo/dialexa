"""Конвертація Helsinki-NLP/opus-mt-de-uk у CTranslate2 (опційний швидкий рушій перекладу).

Запуск (один раз, потрібен torch — встановлюється тільки для конвертації):
    .venv/bin/pip install transformers torch ct2-transformers
    .venv/bin/python tools/convert_opus.py

Результат: каталог моделей (за замовчуванням) ~/Library/Application Support/
lecture-translator/models/opus-mt-de-uk — після цього рушій «opus» доступний
у налаштуваннях.
"""
from __future__ import annotations

from pathlib import Path

import ctranslate2

from lecture_translator.config import models_dir


def main() -> None:
    out = models_dir() / "opus-mt-de-uk"
    out.mkdir(parents=True, exist_ok=True)
    print(f"Конвертую Helsinki-NLP/opus-mt-de-uk -> {out} ...")
    ctranslate2.converters.TransformersConverter(
        "Helsinki-NLP/opus-mt-de-uk", copy_files=["source.spm", "target.spm"]
    ).convert(str(out))
    print("Готово. Оберіть рушій «opus» у налаштуваннях.")


if __name__ == "__main__":
    main()
