"""Causal invariance of features_daily: no row may depend on a later price.

The features are built twice: once on the full history and once on the
history truncated at a cut date T. If every feature only reads rows at or
before its own date, both builds agree exactly on every date <= T. A
centered or forward-looking window breaks the equality.
"""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb
import pytest

from market_elt.dbt_runner import run_dbt
from market_elt.ingest import load_prices
from market_elt.synthetic import write_synthetic_prices

N_TICKERS = 2
N_DAYS = 60
CUT_INDEXES = (25, 45)
FEATURES_SQL = "SELECT * FROM features_daily WHERE price_date <= $cut ORDER BY ticker, price_date"


def _build(csv_path: Path, workdir: Path) -> Path:
    db = workdir / "features.duckdb"
    load_prices(csv_path, db)
    run = run_dbt("build", db, workdir / "target")
    assert run.returncode == 0, run.stdout
    return db


def _features_until(db: Path, cut: str) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(FEATURES_SQL, {"cut": cut}).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def full_history(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[str], Path]:
    workdir = tmp_path_factory.mktemp("full")
    csv_path = write_synthetic_prices(workdir / "full.csv", N_TICKERS, N_DAYS, seed=42)
    with csv_path.open(newline="") as handle:
        dates = sorted({row["date"] for row in csv.DictReader(handle)})
    return csv_path, dates, _build(csv_path, workdir)


def _truncate(csv_path: Path, cut: str, out: Path) -> Path:
    with csv_path.open(newline="") as src, out.open("w", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=list(reader.fieldnames or []))
        writer.writeheader()
        writer.writerows(row for row in reader if row["date"] <= cut)
    return out


@pytest.mark.parametrize("cut_index", CUT_INDEXES)
def test_features_up_to_t_ignore_rows_after_t(
    tmp_path: Path, full_history: tuple[Path, list[str], Path], cut_index: int
) -> None:
    csv_path, dates, full_db = full_history
    cut = dates[cut_index]
    truncated_db = _build(_truncate(csv_path, cut, tmp_path / "cut.csv"), tmp_path)

    expected = _features_until(full_db, cut)
    actual = _features_until(truncated_db, cut)

    assert len(expected) == N_TICKERS * (cut_index + 1)
    assert actual == expected


def test_window_is_filled_after_warmup(full_history: tuple[Path, list[str], Path]) -> None:
    _, dates, full_db = full_history
    con = duckdb.connect(str(full_db), read_only=True)
    try:
        rows = con.execute(
            "SELECT max(n_obs_window), count(rolling_vol_20d), count(*) FROM features_daily"
        ).fetchone()
    finally:
        con.close()
    assert rows is not None
    max_window, non_null_vol, total = rows
    assert max_window == 20
    # the first two dates per ticker have fewer than 2 returns, so no stddev
    assert (non_null_vol, total) == (N_TICKERS * (N_DAYS - 2), N_TICKERS * N_DAYS)
    assert len(dates) == N_DAYS
