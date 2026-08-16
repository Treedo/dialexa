"""Точка входу застосунку.

    python run.py                          — звичайний запуск (захоплення системного звуку)
    python run.py --file лекція.wav --stats — тестовий режим з файлу + статистика затримок
    python run.py --file лекція.wav --speed 0 — швидкий прогін без реального темпу
"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .audio.capture import resolve_device
from .bus import Bus
from .config import Settings
from .pipeline import Pipeline
from .stats import StatsCollector
from .ui.download_dialog import DownloadDialog
from .ui.main_window import MainWindow
from .ui.theme import apply_theme

log = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lecture-translator")
    p.add_argument("--file", metavar="FILE", help="Запустити пайплайн з аудіофайлу (тестовий режим)")
    p.add_argument("--stats", action="store_true", help="Надрукувати статистику затримок (з --file)")
    p.add_argument(
        "--speed", type=float, default=1.0,
        help="Темп подачі файлу (1.0 = реальний час, 0 = без пауз)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    app = QApplication([sys.argv[0]])
    app.setApplicationName("lecture-translator")

    settings = Settings.load()
    apply_theme(settings.ui_dark_mode)
    bus = Bus()
    pipeline = Pipeline(bus, settings)

    if args.file:
        return _file_mode(app, bus, settings, pipeline, args)

    window = MainWindow(bus, settings, pipeline)
    window.show()

    # Перший запуск: діалог вибору пристрою (з гідом по BlackHole)
    if not settings.first_run_done:
        from .ui.device_dialog import DeviceDialog

        dlg = DeviceDialog(bus, settings, window)
        dlg.exec()
        settings.first_run_done = True
        settings.save()

    # Пристрій резолвимо за іменем (BlackHole/loopback/мікрофон): числовий
    # CoreAudio id зі старого конфіга мігруємо на актуальний вибір.
    device = resolve_device(settings.audio_device)
    if device != settings.audio_device:
        settings.audio_device = device or ""
        settings.save()
    pipeline.start(device)

    needed = pipeline.model_manager.needed(settings)
    if needed:
        dlg = DownloadDialog(bus, pipeline.model_manager.cancel_event, needed, window)
        dlg.show()
        window._download_dialog = dlg  # тримаємо посилання, поки відкрито

    rc = app.exec()
    pipeline.stop()
    settings.save()
    return rc


def _file_mode(app, bus, settings, pipeline, args) -> int:
    stats = StatsCollector()
    pipeline.start_file(args.file, speed=args.speed, stats=stats)

    timer = QTimer()
    timer.setInterval(500)

    def poll() -> None:
        if pipeline.file_done.is_set():
            timer.stop()
            if args.stats:
                print(stats.summary())
            app.quit()

    timer.timeout.connect(poll)
    timer.start()
    print(f"Обробляю {args.file} (темп x{args.speed})...")
    rc = app.exec()
    pipeline.stop()
    settings.save()  # зберегти адаптивні налаштування потоків тощо
    if args.stats:
        print(stats.summary())
    return rc
