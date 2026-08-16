"""Головне вікно: панель керування + двомовна стрічка + статусбар."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QToolBar,
)

from ..saver import SessionSaver
from .device_dialog import DeviceDialog
from .settings_dialog import SettingsDialog
from .theme import apply_theme
from .transcript_view import TranscriptView

ASR_MODELS = ("tiny", "base", "small")


class MainWindow(QMainWindow):
    def __init__(self, bus, settings, pipeline=None):
        super().__init__()
        self.bus = bus
        self.settings = settings
        self.pipeline = pipeline
        self.saver = SessionSaver(settings.save_dir, settings.asr_model, settings.audio_device)

        self.setWindowTitle("🎓 Dialexa · DE → UK")
        self.resize(760, 640)

        self.view = TranscriptView(font_size=settings.ui_font_size, dark=settings.ui_dark_mode)
        self.setCentralWidget(self.view)

        self._build_toolbar()
        self._build_statusbar()
        self._wire_bus()

    # ---------- побудова ----------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Керування")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.pause_action = QAction("⏸ Пауза", self)
        self.pause_action.triggered.connect(self._toggle_pause)
        tb.addAction(self.pause_action)

        clear_action = QAction("🗑 Очистити", self)
        clear_action.triggered.connect(self._clear)
        tb.addAction(clear_action)

        save_action = QAction("💾 Зберегти", self)
        save_action.triggered.connect(self._save)
        tb.addAction(save_action)

        tb.addSeparator()

        device_action = QAction("🎧 Джерело звуку", self)
        device_action.triggered.connect(self._choose_device)
        tb.addAction(device_action)

        tb.addSeparator()

        tb.addWidget(QLabel(" Модель:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(ASR_MODELS)
        self.model_combo.setCurrentText(self.settings.asr_model)
        self.model_combo.setToolTip(
            "Розмір моделі розпізнавання. Зміна потребує перезапуску пайплайну."
        )
        self.model_combo.currentTextChanged.connect(self._model_changed)
        tb.addWidget(self.model_combo)

        tb.addSeparator()

        font_dec_action = QAction("A−", self)
        font_dec_action.setToolTip("Зменшити шрифт")
        font_dec_action.triggered.connect(lambda: self._change_font(-1))
        tb.addAction(font_dec_action)

        font_inc_action = QAction("A+", self)
        font_inc_action.setToolTip("Збільшити шрифт")
        font_inc_action.triggered.connect(lambda: self._change_font(+1))
        tb.addAction(font_inc_action)

        tb.addSeparator()

        settings_action = QAction("⚙ Налаштування", self)
        settings_action.triggered.connect(self._open_settings)
        tb.addAction(settings_action)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()

        self.watchdog_label = QLabel("")
        self.watchdog_label.setStyleSheet("color:#f9ab00; padding:0 8px;")
        sb.addWidget(self.watchdog_label)

        self.status_label = QLabel("Готово")
        sb.addWidget(self.status_label, 1)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setFixedSize(90, 12)
        self.level_bar.setTextVisible(False)
        sb.addPermanentWidget(self.level_bar)

        self.skipped_label = QLabel("")
        sb.addPermanentWidget(self.skipped_label)

    # ---------- сигнали bus ----------

    def _wire_bus(self) -> None:
        b = self.bus
        b.german_utterance.connect(self._on_german)
        b.sentence_translated.connect(self._on_ukrainian)
        b.status.connect(self.status_label.setText)
        b.level.connect(self._on_level)
        b.skipped.connect(self._on_skipped)
        b.watchdog.connect(self.watchdog_label.setText)
        b.silence_detected.connect(self._on_silence)

    def _on_german(self, utt_id: int, text: str) -> None:
        from ..translate.sentence_splitter import split_german

        timestamp = time.strftime("%H:%M:%S")
        self.view.add_german_utterance(utt_id, split_german(text), timestamp)
        self.saver.on_german(utt_id, text)

    def _on_ukrainian(self, utt_id: int, idx: int, text: str) -> None:
        self.view.set_ukrainian(utt_id, idx, text)
        self.saver.on_ukrainian(utt_id, idx, text)

    def _on_level(self, level: float) -> None:
        self.level_bar.setValue(int(level * 100))

    def _on_skipped(self, total: int) -> None:
        self.skipped_label.setText(f"пропущено: {total}")

    def _on_silence(self, silent: bool) -> None:
        self.level_bar.setStyleSheet(
            "QProgressBar { background:#5c1a1a; }" if silent else ""
        )
        if silent:
            self.status_label.setText(
                "🔇 Немає звуку — перевірте, що лекція грає у Multi-Output Device"
            )

    # ---------- дії ----------

    def _toggle_pause(self) -> None:
        if self.pipeline is None:
            return
        if self.pipeline.paused:
            self.pipeline.resume()
            self.pause_action.setText("⏸ Пауза")
        else:
            self.pipeline.pause()
            self.pause_action.setText("▶ Продовжити")

    def _clear(self) -> None:
        self.view.clear()
        self.saver.clear()
        if self.pipeline is not None and self.pipeline.asr_worker is not None:
            self.pipeline.asr_worker.reset_context()
        self.skipped_label.setText("")

    def _save(self) -> None:
        if not self.saver.events:
            QMessageBox.information(self, "Збереження", "Сесія порожня — немає що зберігати.")
            return
        path = self.saver.flush()
        QMessageBox.information(self, "Збережено", f"Конспект збережено:\n{path}")

    def _choose_device(self) -> None:
        dlg = DeviceDialog(self.bus, self.settings, self)
        if dlg.exec() and self.pipeline is not None:
            self.pipeline.switch_device(self.settings.audio_device)
            self.status_label.setText(f"🎧 {self.settings.audio_device}")

    def _change_font(self, delta: int) -> None:
        size = max(8, min(24, self.settings.ui_font_size + delta))
        if size == self.settings.ui_font_size:
            return
        self.settings.ui_font_size = size
        self.settings.save()
        self.view.set_font_size(size)

    def _model_changed(self, name: str) -> None:
        if name == self.settings.asr_model:
            return
        self.settings.asr_model = name
        self.settings.save()
        if self.pipeline is not None and self.pipeline.running:
            QMessageBox.information(
                self,
                "Перезапуск",
                "Модель змінено — пайплайн перезапускається (якщо моделі немає, "
                "її буде завантажено, це може зайняти час).",
            )
            self.pipeline.restart()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            apply_theme(self.settings.ui_dark_mode)
            self.view.set_font_size(self.settings.ui_font_size)
            self.view.set_dark(self.settings.ui_dark_mode)
            self.status_label.setText("Налаштування збережено")

    # ---------- закриття ----------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-сигнатура)
        if self.saver.events:
            self.saver.flush()  # автосейв сесії
        if self.pipeline is not None:
            self.pipeline.stop()
        self.settings.save()
        super().closeEvent(event)
