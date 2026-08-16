#!/usr/bin/env bash
# Збірка Dialexa.app (macOS) з поточного оточення.
# Використання: tools/build_macos_app.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PY:-.venv/bin/python}

echo "==> Перевіряю PyInstaller..."
"$PY" -c "import PyInstaller" 2>/dev/null || "$PY" -m pip install "pyinstaller>=6.10"

echo "==> Генерую іконку (.icns)..."
"$PY" tools/make_icon.py

echo "==> Збираю бандл..."
"$PY" -m PyInstaller --clean --noconfirm packaging/dialexa.spec

echo "==> Підписую ad-hoc (запуск без «пошкодженого застосунку» на цьому Mac)..."
codesign --force --deep --sign - dist/Dialexa.app

echo "✅ Готово: dist/Dialexa.app"
echo "   Студентам: скопіюйте .app у /Applications і відкрийте (перший запуск — правий клік → Відкрити)."
