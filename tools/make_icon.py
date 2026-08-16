"""Генерує packaging/dialexa.icns з QPainter (без зовнішніх залежностей).

Малює: індиго-градієнтна плитка, біла звукова хвиля (мікрофон) і підпис De→Ук.
Потім iconutil (macOS) пакує PNG у .icns для бандла.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

QT_QPA_PLATFORM = "offscreen"

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ICONSET = ROOT / "packaging" / "dialexa.iconset"
ICNS = ROOT / "packaging" / "dialexa.icns"

MASTER = 1024


def draw_master() -> QImage:
    img = QImage(MASTER, MASTER, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # плитка з градієнтом індиго → синій
    grad = QLinearGradient(0, 0, MASTER, MASTER)
    grad.setColorAt(0.0, QColor("#4338ca"))
    grad.setColorAt(1.0, QColor("#1d4ed8"))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, MASTER, MASTER), MASTER * 0.22, MASTER * 0.22)

    # звукова хвиля: 7 білих смужок навколо центру
    heights = [120, 210, 300, 380, 300, 210, 120]
    bar_w = MASTER * 0.075
    gap = MASTER * 0.035
    total = len(heights) * bar_w + (len(heights) - 1) * gap
    x0 = (MASTER - total) / 2
    y0 = MASTER * 0.30
    p.setBrush(QColor("#ffffff"))
    p.setPen(Qt.PenStyle.NoPen)
    for i, h in enumerate(heights):
        y = y0 + (max(heights) - h) / 2
        p.drawRoundedRect(QRectF(x0 + i * (bar_w + gap), y, bar_w, h), bar_w / 2, bar_w / 2)

    # підпис
    font = QFont("Helvetica Neue", int(MASTER * 0.14))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(QRectF(0, MASTER * 0.62, MASTER, MASTER * 0.30),
               Qt.AlignmentFlag.AlignCenter, "De→Ук")
    p.end()
    return img


def main() -> int:
    app = QApplication([])  # noqa: F841 — потрібен QPainter
    master = draw_master()

    ICONSET.mkdir(parents=True, exist_ok=True)
    spec = {
        "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
    }
    for name, size in spec.items():
        scaled = master.scaled(size, size,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        ok = scaled.save(str(ICONSET / name), "PNG")
        assert ok, f"не вдалося зберегти {name}"

    subprocess.run(["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)], check=True)
    print(f"✅ {ICNS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
