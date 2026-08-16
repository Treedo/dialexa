"""Явна світла/темна тема застосунку (незалежно від системного вигляду macOS).

Без цього Qt наслідує системну тему: на Mac із темним оформленням «світла тема»
давала б темні панелі зі світлим текстом і навпаки.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(dark: bool) -> None:
    """Застосовує тему до всього застосунку (вікно, діалоги, панелі)."""
    app = QApplication.instance()
    if app is None:
        return
    app.setStyle("Fusion")
    if not dark:
        app.setPalette(QApplication.style().standardPalette())
        return

    pal = QPalette()
    bg = QColor("#202124")
    panel = QColor("#2b2d31")
    text = QColor("#e8eaed")
    muted = QColor("#9aa0a6")
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, bg)
    pal.setColor(QPalette.ColorRole.AlternateBase, panel)
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, panel)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#4f6ef7"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, panel)
    pal.setColor(QPalette.ColorRole.ToolTipText, text)
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorRole.Link, QColor("#8ab4f8"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#ff6b6b"))
    app.setPalette(pal)
