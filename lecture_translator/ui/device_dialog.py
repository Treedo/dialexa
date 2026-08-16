"""Діалог вибору джерела звуку: список пристроїв, гід по BlackHole, тест рівня."""
from __future__ import annotations

import platform
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..audio.capture import AudioCapture, find_blackhole, find_default_loopback, list_input_devices

BLACKHOLE_GUIDE = (
    "<b>❌ BlackHole не знайдено.</b> Встановіть його один раз:<br><br>"
    "1) У терміналі: <code>brew install blackhole-2ch</code><br>"
    "&nbsp;&nbsp;&nbsp;(або завантажте з existential.audio)<br>"
    "2) Відкрийте <b>Audio MIDI Setup</b> (у Програми/Утиліти)<br>"
    "3) Кнопка <b>+</b> внизу ліворуч → <b>Create Multi-Output Device</b><br>"
    "4) Позначте <b>BlackHole 2ch</b> і ваші колонки/навушники<br>"
    "5) Оберіть Multi-Output Device як пристрій виводу (меню гучності 🎧)<br>"
    "6) Натисніть «Перевірити знову» нижче<br><br>"
    "<i>Примітка: під час роботи Multi-Output Device клавіші гучності можуть не працювати — "
    "регулюйте гучність у самому застосунку лекції.</i>"
)


class DeviceDialog(QDialog):
    def __init__(self, bus, settings, parent=None):
        super().__init__(parent)
        self.bus = bus
        self.settings = settings
        self._probe: AudioCapture | None = None
        self._probe_stop: threading.Event | None = None

        self.setWindowTitle("Джерело звуку")
        self.setMinimumWidth(620)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Оберіть пристрій, з якого читати звук лекції:"))

        self.listw = QListWidget()
        self.listw.currentItemChanged.connect(self._start_probe)
        lay.addWidget(self.listw)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.hint)

        self.refresh_btn = QPushButton("🔄 Перевірити знову")
        self.refresh_btn.clicked.connect(self._refresh)
        lay.addWidget(self.refresh_btn)

        level_row = QVBoxLayout()
        level_row.addWidget(QLabel("Рівень вхідного сигналу (увімкніть лекцію для перевірки):"))
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        level_row.addWidget(self.level_bar)
        lay.addLayout(level_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#d93025;")
        self.error_label.setWordWrap(True)
        lay.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.bus.level.connect(self._on_level)
        self._refresh()

    # ---------- список пристроїв ----------

    def _refresh(self) -> None:
        self.listw.clear()
        devices = list_input_devices()
        selection = -1
        for i, d in enumerate(devices):
            tag = "  [Loopback]" if d["loopback"] else ""
            item = QListWidgetItem(f"{d['name']}{tag}")
            # ключ — ім'я пристрою: CoreAudio id нестабільні, а soundcard
            # на macOS зіставляє лише числові id, які ми не зберігаємо
            item.setData(Qt.ItemDataRole.UserRole, d["name"])
            self.listw.addItem(item)
            if self.settings.audio_device and d["name"] == self.settings.audio_device:
                selection = i
        if selection < 0:
            if platform.system() == "Darwin":
                bh = find_blackhole(devices)
                if bh:
                    for i in range(self.listw.count()):
                        if self.listw.item(i).text().startswith(bh):
                            selection = i
                            break
            else:
                lb = find_default_loopback(devices)
                if lb:
                    for i in range(self.listw.count()):
                        if self.listw.item(i).text().startswith(lb):
                            selection = i
                            break
        if selection < 0 and self.listw.count():
            selection = 0
        if selection >= 0:
            self.listw.setCurrentRow(selection)
        self._update_hint(devices)

    def _update_hint(self, devices: list[dict]) -> None:
        if platform.system() == "Darwin":
            if find_blackhole(devices):
                self.hint.setText(
                    "✅ BlackHole знайдено. Оберіть «BlackHole 2ch» у списку.<br>"
                    "<i>Переконайтеся, що в Audio MIDI Setup створено Multi-Output Device "
                    "і системний звук виведено в нього.</i>"
                )
            else:
                self.hint.setText(BLACKHOLE_GUIDE)
        else:
            self.hint.setText(
                "Windows: оберіть <b>loopback-пристрій</b> того виходу, на якому грає лекція "
                "(драйвери не потрібні)."
            )

    # ---------- пробне захоплення ----------

    def _start_probe(self, _cur=None, _prev=None) -> None:
        self._stop_probe()
        item = self.listw.currentItem()
        if item is None:
            return
        device_id = item.data(Qt.ItemDataRole.UserRole)
        self._probe_stop = threading.Event()
        self._probe = AudioCapture(
            self.bus, device_id, vad_queue=None, ring=None, stop_event=self._probe_stop
        )
        self._probe.start()

    def _stop_probe(self) -> None:
        if self._probe_stop is not None:
            self._probe_stop.set()
        self._probe = None
        self._probe_stop = None

    def _on_level(self, level: float) -> None:
        self.level_bar.setValue(int(level * 100))

    # ---------- завершення ----------

    def accept(self) -> None:
        item = self.listw.currentItem()
        if item is not None:
            self.settings.audio_device = str(item.data(Qt.ItemDataRole.UserRole))
        self.settings.save()
        self._stop_probe()
        super().accept()

    def reject(self) -> None:
        self._stop_probe()
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-сигнатура)
        self._stop_probe()
        super().closeEvent(event)
