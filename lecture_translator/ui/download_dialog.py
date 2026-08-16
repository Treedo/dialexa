"""Немодальний діалог завантаження моделей (прогрес + скасування).

Застосунок працює, поки моделі вантажаться; ASR/переклад стартують,
щойно завантаження завершено (ready_event).
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class DownloadDialog(QDialog):
    def __init__(self, bus, cancel_event, names: list[str], parent=None):
        super().__init__(parent)
        self.bus = bus
        self.cancel_event = cancel_event
        self.bars: dict[str, QProgressBar] = {}
        self._done: dict[str, bool] = {}

        self.setWindowTitle("Завантаження моделей")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel("Завантажую моделі (один раз, ~1.7 ГБ).\n"
                   "Можна працювати в застосунку — розпізнавання стартує після завершення.")
        )
        for name in names:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat(f"{name}  %p%")
            self.bars[name] = bar
            self._done[name] = False
            lay.addWidget(bar)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self.cancel_btn = QPushButton("Скасувати")
        self.cancel_btn.clicked.connect(self._cancel)
        lay.addWidget(self.cancel_btn)

        self.close_btn = QPushButton("Закрити")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        lay.addWidget(self.close_btn)

        self.bus.download_progress.connect(self._on_progress)
        self.bus.download_done.connect(self._on_done)

    def _on_progress(self, name: str, done: int, total: int) -> None:
        bar = self.bars.get(name)
        if bar is None:
            return
        if total > 0:
            bar.setRange(0, total)
            bar.setValue(min(done, total))
            bar.setFormat(f"{name}  %p%")
        else:
            bar.setRange(0, 0)  # невідомий розмір — «біжучий» індикатор

    def _on_done(self, name: str, ok: bool, msg: str) -> None:
        self._done[name] = True
        bar = self.bars.get(name)
        if bar is not None and ok:
            bar.setRange(0, 1)
            bar.setValue(1)
            bar.setFormat(f"{name}  ✓")
        if all(self._done.values()):
            self.status.setText("Готово. Розпізнавання і переклад запущено.")
            self.cancel_btn.setEnabled(False)
            self.close_btn.setEnabled(True)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_btn.setEnabled(False)
        self.status.setText("Скасовую... (можна повторити пізніше через перезапуск)")
