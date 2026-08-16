# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для Dialexa.app (macOS).

Збірка: tools/build_macos_app.sh (або python -m PyInstaller packaging/dialexa.spec)
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# SPECPATH може бути шляхом до spec-файла або до його каталогу — нормалізуємо
SPEC_DIR = Path(SPECPATH).resolve()
if SPEC_DIR.suffix == ".spec":
    SPEC_DIR = SPEC_DIR.parent
ROOT = SPEC_DIR                             # packaging/
PROJECT = ROOT.parent                       # корінь репозиторію

# Рантайм-дані: cffi-заголовки soundcard (coreaudio.py.h) читаються з диска,
# faster_whisper несе mel_filters.npz / silero VAD-модель у пакеті.
datas = collect_data_files("soundcard")
datas += collect_data_files("faster_whisper")

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        # невикористовувані Qt-модулі (зменшує бандл)
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtMultimedia",
        "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
        "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtWebSockets",
        "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtRemoteObjects",
        "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Dialexa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # віконний застосунок без термінала
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Dialexa")

app = BUNDLE(
    coll,
    name="Dialexa.app",
    icon=str(ROOT / "dialexa.icns"),
    bundle_identifier="com.dialexa.translator",
    info_plist={
        "CFBundleDisplayName": "dialexa",
        "CFBundleShortVersionString": "0.2.0",
        "NSHighResolutionCapable": True,
        # дозвіл на запис звуку (TCC) для пристроїв-мікрофонів
        "NSMicrophoneUsageDescription": "Dialexa записує звук лекції для перекладу.",
        "LSMinimumSystemVersion": "12.0",
    },
)
