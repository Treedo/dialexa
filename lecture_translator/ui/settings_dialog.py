"""Діалог налаштувань: ASR, переклад, VAD, інтерфейс."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Налаштування")
        self.setMinimumWidth(460)

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # --- ASR ---
        self.asr_model = QComboBox()
        self.asr_model.addItems(["tiny", "base", "small"])
        self.asr_model.setCurrentText(settings.asr_model)
        form.addRow("Модель розпізнавання", self.asr_model)

        self.asr_beam = QSpinBox()
        self.asr_beam.setRange(1, 5)
        self.asr_beam.setValue(settings.asr_beam_size)
        form.addRow("ASR beam_size (швидкість/якість)", self.asr_beam)

        self.asr_threads = QSpinBox()
        self.asr_threads.setRange(1, 32)
        self.asr_threads.setValue(settings.asr_cpu_threads)
        form.addRow("ASR: потоки CPU", self.asr_threads)

        self.prev_chars = QSpinBox()
        self.prev_chars.setRange(0, 5000)
        self.prev_chars.setValue(settings.asr_previous_text_max_chars)
        form.addRow("Контекст попереднього тексту (симв.)", self.prev_chars)

        # --- переклад ---
        self.engine = QComboBox()
        self.engine.addItem("NLLB-600M (рекомендовано)", "nllb")
        self.engine.addItem("opus-mt-de-uk (експериментально)", "opus")
        idx = self.engine.findData(settings.translation_engine)
        self.engine.setCurrentIndex(max(0, idx))
        form.addRow("Рушій перекладу", self.engine)

        self.mt_beam = QSpinBox()
        self.mt_beam.setRange(1, 5)
        self.mt_beam.setValue(settings.translation_beam_size)
        form.addRow("Переклад beam_size", self.mt_beam)

        self.mt_threads = QSpinBox()
        self.mt_threads.setRange(1, 32)
        self.mt_threads.setValue(settings.translation_intra_threads)
        form.addRow("Переклад: потоки CPU", self.mt_threads)

        # --- VAD ---
        self.vad_thr = QDoubleSpinBox()
        self.vad_thr.setRange(0.1, 0.9)
        self.vad_thr.setSingleStep(0.05)
        self.vad_thr.setValue(settings.vad_threshold)
        form.addRow("VAD: поріг мови", self.vad_thr)

        self.vad_sil = QSpinBox()
        self.vad_sil.setRange(100, 3000)
        self.vad_sil.setValue(settings.vad_silence_ms)
        form.addRow("VAD: хвіст тиші (мс)", self.vad_sil)

        self.vad_min = QSpinBox()
        self.vad_min.setRange(100, 2000)
        self.vad_min.setValue(settings.vad_min_speech_ms)
        form.addRow("VAD: мін. тривалість мови (мс)", self.vad_min)

        self.vad_max = QSpinBox()
        self.vad_max.setRange(2000, 30000)
        self.vad_max.setValue(settings.vad_max_utterance_ms)
        form.addRow("VAD: макс. висловлювання (мс)", self.vad_max)

        self.vad_pad = QSpinBox()
        self.vad_pad.setRange(0, 1000)
        self.vad_pad.setValue(settings.vad_pad_ms)
        form.addRow("VAD: пад до/після мови (мс)", self.vad_pad)

        # --- інтерфейс ---
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 24)
        self.font_size.setValue(settings.ui_font_size)
        form.addRow("Розмір шрифту", self.font_size)

        self.dark = QCheckBox("Темна тема")
        self.dark.setChecked(settings.ui_dark_mode)
        form.addRow("", self.dark)

        row = QHBoxLayout()
        self.save_dir = QLineEdit(settings.save_dir)
        browse = QPushButton("Обрати...")
        browse.clicked.connect(self._browse)
        row.addWidget(self.save_dir)
        row.addWidget(browse)
        form.addRow("Каталог збереження", row)

        lay.addLayout(form)

        note = QLabel(
            "Зміни моделі/потоків/VAD застосуються після перезапуску пайплайну "
            "(перезапустіть застосунок або змініть модель)."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#9aa0a6;")
        lay.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Каталог збереження", self.save_dir.text())
        if path:
            self.save_dir.setText(path)

    def _accept(self) -> None:
        s = self.settings
        s.asr_model = self.asr_model.currentText()
        s.asr_beam_size = self.asr_beam.value()
        s.asr_cpu_threads = self.asr_threads.value()
        s.asr_previous_text_max_chars = self.prev_chars.value()
        s.translation_engine = self.engine.currentData()
        s.translation_beam_size = self.mt_beam.value()
        s.translation_intra_threads = self.mt_threads.value()
        s.vad_threshold = self.vad_thr.value()
        s.vad_silence_ms = self.vad_sil.value()
        s.vad_min_speech_ms = self.vad_min.value()
        s.vad_max_utterance_ms = self.vad_max.value()
        s.vad_pad_ms = self.vad_pad.value()
        s.ui_font_size = self.font_size.value()
        s.ui_dark_mode = self.dark.isChecked()
        s.save_dir = self.save_dir.text() or str(Path.home() / "Documents" / "lecture-translator-sessions")
        s.save()
        super().accept()
