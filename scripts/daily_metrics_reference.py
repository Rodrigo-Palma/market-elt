"""Independent reference for the daily_metrics unit test.

Recomputes the expected rows of the dbt unit test with the Python standard
library (exact two-pass ``statistics.stdev``), from the definition and not
from the SQL. ``tests/test_unit_test_reference.py`` checks that the
expectations in ``transform/models/marts/_marts.yml`` match this output.

Run: uv run python scripts/daily_metrics_reference.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from itertools import pairwise
from typing import Final

TRADING_DAYS: Final = 252
VOL_DECIMALS: Final = 10

# (price_date, ticker, close), deliberately out of date order.
INPUT_ROWS: Final[tuple[tuple[str, str, float], ...]] = (
    ("2026-01-05", "AAA", 101.0),
    ("2026-01-01", "AAA", 100.0),
    ("2026-01-03", "AAA", 99.0),
    ("2026-01-02", "AAA", 102.0),
    ("2026-01-02", "BBB", 20.0),
    ("2026-01-02", "CCC", 50.0),
    ("2026-01-01", "CCC", 40.0),
)


def reference_metrics(
    rows: tuple[tuple[str, str, float], ...],
) -> list[dict[str, object]]:
    """Expected daily_metrics rows for ``rows``, sorted by ticker."""
    by_ticker: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for price_date, ticker, close in rows:
        by_ticker[ticker].append((price_date, close))
    expected: list[dict[str, object]] = []
    for ticker in sorted(by_ticker):
        series = sorted(by_ticker[ticker])
        closes = [close for _, close in series]
        returns = [today / yesterday - 1 for yesterday, today in pairwise(closes)]
        volatility = (
            round(statistics.stdev(returns) * math.sqrt(TRADING_DAYS), VOL_DECIMALS)
            if len(returns) >= 2
            else None
        )
        expected.append(
            {
                "ticker": ticker,
                "observations": len(series),
                "last_date": series[-1][0],
                "last_close": closes[-1],
                "annualized_volatility": volatility,
            }
        )
    return expected


if __name__ == "__main__":
    for row in reference_metrics(INPUT_ROWS):
        print(row)
