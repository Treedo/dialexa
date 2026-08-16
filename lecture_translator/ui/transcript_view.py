"""Двомовна стрічка лекції: німецький оригінал (сірий, дрібний) + український переклад.

Кожне речення — пара міток; українська заповнюється на місці, щойно переклад готовий.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

MAX_UTTERANCES = 500  # ліміт історії (старі висловлювання відкидаються)


class TranscriptView(QScrollArea):
    def __init__(self, parent=None, font_size: int = 13, dark: bool = True):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self._lay = QVBoxLayout(container)
        self._lay.setContentsMargins(8, 8, 8, 8)
        self._lay.setSpacing(4)
        self._lay.addStretch(1)
        self.setWidget(container)

        self.font_size = font_size
        self.dark = dark
        self._rows: dict[tuple[int, int], tuple[QLabel, QLabel]] = {}
        self._utt_frames: dict[int, QFrame] = {}

        # автопрокрутка: стежимо за «хвостом», поки користувач сам не піднявся вище.
        # rangeChanged приходить ПІСЛЯ layout-у, тож прокрутка завжди бачить
        # фінальний максимум (QTimer.singleShot не гарантує порядку подій)
        self._follow_tail = True
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_value)
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)
        self.set_dark(dark)

    # ---------- стилі ----------

    def _style_de(self) -> str:
        color = "#9aa0a6" if self.dark else "#5f6368"
        return f"color:{color}; font-size:{self.font_size - 1}pt;"

    def _style_uk(self) -> str:
        color = "#e8eaed" if self.dark else "#202124"
        return f"color:{color}; font-size:{self.font_size}pt;"

    def _style_time(self) -> str:
        color = "#6b7280" if self.dark else "#9aa0a6"
        return f"color:{color}; font-size:{self.font_size - 3}pt;"

    def set_font_size(self, size: int) -> None:
        self.font_size = size
        for de, uk in self._rows.values():
            de.setStyleSheet(self._style_de())
            uk.setStyleSheet(self._style_uk())

    def set_dark(self, dark: bool) -> None:
        self.dark = dark
        bg = "#202124" if dark else "#ffffff"
        # явний фон стрічки — тема не залежить від системного вигляду macOS
        self.setStyleSheet(f"QScrollArea {{ background: {bg}; border: none; }}")
        self.widget().setStyleSheet(f"QWidget {{ background: {bg}; }}")
        self.set_font_size(self.font_size)

    # ---------- API ----------

    def add_german_utterance(self, utt_id: int, sentences: list[str], timestamp: str = "") -> None:
        """Створює блок висловлювання: мітка часу, німецькі рядки, українські — «…»."""
        frame = QFrame()
        frame.setObjectName("uttFrame")
        border = "#3c4043" if self.dark else "#dadce0"
        frame.setStyleSheet(
            f"QFrame#uttFrame {{ border-bottom: 1px solid {border}; margin-bottom: 6px; }}"
        )
        flay = QVBoxLayout(frame)
        flay.setContentsMargins(0, 0, 0, 4)
        flay.setSpacing(2)

        if timestamp:
            time_label = QLabel(f"🕐 {timestamp}")
            time_label.setStyleSheet(self._style_time())
            flay.addWidget(time_label)

        for idx, sent in enumerate(sentences):
            de = QLabel(sent)
            de.setWordWrap(True)
            de.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            de.setStyleSheet(self._style_de())

            uk = QLabel("▶ …")
            uk.setWordWrap(True)
            uk.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            uk.setStyleSheet(self._style_uk())

            flay.addWidget(de)
            flay.addWidget(uk)
            self._rows[(utt_id, idx)] = (de, uk)

        self._lay.insertWidget(self._lay.count() - 1, frame)
        self._utt_frames[utt_id] = frame
        self._trim()
        self._autoscroll()

    def set_ukrainian(self, utt_id: int, idx: int, text: str) -> None:
        row = self._rows.get((utt_id, idx))
        if row is not None:
            row[1].setText("▶ " + text)
            self._autoscroll()

    def clear(self) -> None:
        for frame in self._utt_frames.values():
            self._lay.removeWidget(frame)
            frame.deleteLater()
        self._utt_frames.clear()
        self._rows.clear()

    # ---------- внутрішнє ----------

    def _trim(self) -> None:
        while len(self._utt_frames) > MAX_UTTERANCES:
            oldest_id = next(iter(self._utt_frames))
            frame = self._utt_frames.pop(oldest_id)
            self._lay.removeWidget(frame)
            frame.deleteLater()
            for k in list(self._rows):
                if k[0] == oldest_id:
                    del self._rows[k]

    def _on_scroll_value(self, value: int) -> None:
        bar = self.verticalScrollBar()
        self._follow_tail = value >= bar.maximum() - 40

    def _on_range_changed(self, _minimum: int, maximum: int) -> None:
        if self._follow_tail:
            self.verticalScrollBar().setValue(maximum)

    def _autoscroll(self) -> None:
        # негайна спроба; rangeChanged доб'є до фінального максимуму після layout
        self._scroll_if_following()

    def _scroll_if_following(self) -> None:
        if self._follow_tail:
            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())
