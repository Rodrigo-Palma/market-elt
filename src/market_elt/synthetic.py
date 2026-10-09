"""Deterministic SYNTHETIC prices, for scale benchmarks and causality tests.

Not market data: each ticker is a geometric random walk with daily log-return
noise N(0, 0.02), on weekdays starting 2020-01-01. Same seed, same bytes.
Tickers are named SYN0000, SYN0001, ... so the data can never be mistaken
for a real feed.
"""

from __future__ import annotations

import csv
import math
import random
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Final

START: Final = date(2020, 1, 1)
DAILY_SIGMA: Final = 0.02
START_PRICE: Final = 100.0


def _weekdays(n_days: int) -> list[date]:
    days: list[date] = []
    current = START
    while len(days) < n_days:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _rows(n_tickers: int, n_days: int, seed: int) -> Iterator[tuple[str, str, str]]:
    rng = random.Random(seed)
    days = [d.isoformat() for d in _weekdays(n_days)]
    for index in range(n_tickers):
        ticker = f"SYN{index:04d}"
        price = START_PRICE
        for day in days:
            price *= math.exp(rng.gauss(0.0, DAILY_SIGMA))
            yield day, ticker, f"{price:.4f}"


def write_synthetic_prices(path: Path, n_tickers: int, n_days: int, seed: int) -> Path:
    """Write ``n_tickers * n_days`` synthetic rows to ``path`` in the raw contract."""
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "close"])
        writer.writerows(_rows(n_tickers, n_days, seed))
    return path
