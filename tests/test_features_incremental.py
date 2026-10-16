"""features_daily built incrementally equals features_daily built from scratch.

The history is loaded in three stages (up to T1, then T2, then T3) into one
database, with an incremental dbt build after each load. A second database
loads the whole history once and builds with ``--full-refresh``. Both tables
must hold exactly the same rows.

The synthetic tickers are shaped around the classic failure of an
incremental rolling window, a window cut at the batch edge: missing trading
days right at each stage boundary, a ticker that first trades after T1, one
that stops trading before T1 and one with a single row before T1.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import duckdb
import pytest

from market_elt.dbt_runner import run_dbt
from market_elt.ingest import load_prices

N_DAYS: Final = 60
STAGES: Final = (40, 47, N_DAYS - 1)  # last day index loaded at each stage
SEED: Final = 7

# ticker -> day indexes it trades on
TRADING_DAYS: Final[dict[str, frozenset[int]]] = {
    "SYNA": frozenset(range(N_DAYS)),
    "SYNB": frozenset(range(N_DAYS)) - {10, 25, 38, 40, 41, 46, 48},
    "SYNC": frozenset(range(43, N_DAYS)) - {50},
    "SYND": frozenset(range(36)),
    "SYNE": frozenset({40, 44, 45, 47, *range(49, N_DAYS)}),
}

FEATURES_SQL: Final = "SELECT * FROM {db}.features_daily"


def _days() -> list[str]:
    days: list[str] = []
    current = date(2021, 1, 1)
    while len(days) < N_DAYS:
        if current.weekday() < 5:
            days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _write_prices(path: Path, last_index: int) -> Path:
    """Prices for every ticker up to day ``last_index``; same values in every file."""
    rng = random.Random(SEED)
    days = _days()
    rows: list[tuple[str, str, str]] = []
    for ticker, trading in TRADING_DAYS.items():
        price = 100.0
        for index, day in enumerate(days):
            price *= math.exp(rng.gauss(0.0, 0.02))
            if index in trading and index <= last_index:
                rows.append((day, ticker, f"{price:.4f}"))
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "close"])
        writer.writerows(rows)
    return path


def _load_and_build(workdir: Path, db: Path, last_index: int, *extra: str) -> None:
    load_prices(_write_prices(workdir / f"prices_{last_index}.csv", last_index), db)
    run = run_dbt("build", db, workdir / "target", extra)
    assert run.returncode == 0, run.stdout


def _fetch(sql: str, inc: Path, full: Path) -> list[tuple[object, ...]]:
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{inc}' AS inc (READ_ONLY)")
        con.execute(f"ATTACH '{full}' AS full_db (READ_ONLY)")
        return con.execute(sql).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    inc_dir = tmp_path_factory.mktemp("incremental")
    inc = inc_dir / "inc.duckdb"
    for last_index in STAGES:
        _load_and_build(inc_dir, inc, last_index)

    full_dir = tmp_path_factory.mktemp("full_refresh")
    full = full_dir / "full.duckdb"
    _load_and_build(full_dir, full, STAGES[-1], "--full-refresh")
    return inc, full


def test_incremental_minus_full_refresh_is_empty(built: tuple[Path, Path]) -> None:
    inc, full = built
    sql = f"{FEATURES_SQL.format(db='inc')} EXCEPT ALL {FEATURES_SQL.format(db='full_db')}"
    assert _fetch(sql, inc, full) == []


def test_full_refresh_minus_incremental_is_empty(built: tuple[Path, Path]) -> None:
    inc, full = built
    sql = f"{FEATURES_SQL.format(db='full_db')} EXCEPT ALL {FEATURES_SQL.format(db='inc')}"
    assert _fetch(sql, inc, full) == []


def test_row_counts_match_the_source(built: tuple[Path, Path]) -> None:
    inc, full = built
    counts = _fetch(
        "SELECT (SELECT count(*) FROM inc.features_daily),"
        " (SELECT count(*) FROM full_db.features_daily)",
        inc,
        full,
    )
    expected = sum(len(days) for days in TRADING_DAYS.values())
    assert counts == [(expected, expected)]


def test_full_window_is_reached_across_the_stage_boundaries(built: tuple[Path, Path]) -> None:
    inc, full = built
    # SYNA trades every day, so from day 20 on its window holds 20 returns
    rows = _fetch(
        "SELECT min(n_obs_window) FROM inc.features_daily"
        f" WHERE ticker = 'SYNA' AND price_date > '{_days()[STAGES[0]]}'",
        inc,
        full,
    )
    assert rows == [(20,)]


def test_incremental_build_leaves_loaded_rows_untouched(tmp_path: Path) -> None:
    """A second build that rebuilt the table would overwrite the sentinel."""
    db = tmp_path / "sentinel.duckdb"
    _load_and_build(tmp_path, db, STAGES[0])
    con = duckdb.connect(str(db))
    try:
        con.execute("UPDATE features_daily SET close = -1 WHERE ticker = 'SYND'")
    finally:
        con.close()

    _load_and_build(tmp_path, db, STAGES[1])

    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            "SELECT count(*), min(close), max(close) FROM features_daily WHERE ticker = 'SYND'"
        ).fetchall()
    finally:
        con.close()
    assert rows == [(len(TRADING_DAYS["SYND"]), -1.0, -1.0)]
