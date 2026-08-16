"""Збір статистики затримок для режиму --file --stats."""
from __future__ import annotations

import time


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(len(s) * p)))
    return s[idx]


class StatsCollector:
    def __init__(self):
        self.rows: list[dict] = []  # {utt_id, t_end, t_german, t_ukr}
        self._by_id: dict[int, dict] = {}

    def on_utterance(self, utt_id: int, t_end: float, t_german: float) -> None:
        row = {"utt_id": utt_id, "t_end": t_end, "t_german": t_german, "t_ukr": None}
        self.rows.append(row)
        self._by_id[utt_id] = row

    def on_translated(self, utt_id: int, t_first_ukr: float) -> None:
        row = self._by_id.get(utt_id)
        if row is not None and row["t_ukr"] is None:
            row["t_ukr"] = t_first_ukr

    def summary(self) -> str:
        n = len(self.rows)
        if n == 0:
            return "висловлювань: 0"
        asr_lat = [r["t_german"] - r["t_end"] for r in self.rows]
        translated = [r for r in self.rows if r["t_ukr"] is not None]
        mt_lat = [r["t_ukr"] - r["t_german"] for r in translated]
        total_lat = [r["t_ukr"] - r["t_end"] for r in translated]
        lines = [
            f"висловлювань: {n}, перекладено: {len(translated)} "
            f"({100 * len(translated) / n:.0f}%)",
            f"затримка ASR (сек):     p50={_percentile(asr_lat, .5):.2f} "
            f"p90={_percentile(asr_lat, .9):.2f}",
        ]
        if mt_lat:
            lines.append(
                f"затримка перекладу (сек): p50={_percentile(mt_lat, .5):.2f} "
                f"p90={_percentile(mt_lat, .9):.2f}"
            )
            lines.append(
                f"загальна затримка (сек):  p50={_percentile(total_lat, .5):.2f} "
                f"p90={_percentile(total_lat, .9):.2f}"
            )
        return "\n".join(lines)

    def run_time(self) -> float:
        return 0.0 if not self.rows else time.time() - min(r["t_end"] for r in self.rows)
