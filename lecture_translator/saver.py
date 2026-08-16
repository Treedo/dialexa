"""Збереження сесії у Markdown: двомовний конспект лекції."""
from __future__ import annotations

import time
from pathlib import Path


def _ts() -> str:
    return time.strftime("%H:%M:%S")


class SessionSaver:
    """Накопичує події (німецькі висловлювання + українські речення)
    і пише їх у файл у порядку висловлювань при flush()."""

    def __init__(self, save_dir: str, model_name: str = "", device: str = ""):
        self.path = Path(save_dir) / f"{time.strftime('%Y-%m-%d_%H%M')}_lecture.md"
        self.model_name = model_name
        self.device = device
        self.events: list[tuple[int, str, str]] = []  # (utt_id, time, рядок md)

    def on_german(self, utt_id: int, text: str) -> None:
        self.events.append((utt_id, _ts(), f"**DE:** {text}"))

    def on_ukrainian(self, utt_id: int, idx: int, text: str) -> None:
        self.events.append((utt_id, _ts(), f"**UKR:** {text}"))

    def flush(self) -> Path:
        """Записує всі події у файл (сортування стабільне: за utt_id, час, порядок)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# Лекція — {time.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Модель: {self.model_name} · Пристрій: {self.device or '—'}",
            "",
        ]
        # стабільне сортування: групуємо за utt_id, усередині — порядок додавання
        grouped: dict[int, list[str]] = {}
        times: dict[int, str] = {}
        for utt_id, t, line in self.events:
            grouped.setdefault(utt_id, []).append(line)
            times.setdefault(utt_id, t)  # час першого рядка (німецького) висловлювання
        for utt_id in sorted(grouped):
            lines.append(f"**🕐 {times[utt_id]}**")
            lines.extend(grouped[utt_id])
            lines.append("---")
            lines.append("")
        self.path.write_text("\n".join(lines), encoding="utf-8")
        return self.path

    def clear(self) -> None:
        self.events.clear()
