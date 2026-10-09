"""Tests for the deterministic synthetic price generator."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from market_elt.ingest import load_prices
from market_elt.synthetic import write_synthetic_prices


def test_same_seed_writes_identical_files(tmp_path: Path) -> None:
    a = write_synthetic_prices(tmp_path / "a.csv", n_tickers=3, n_days=50, seed=7)
    b = write_synthetic_prices(tmp_path / "b.csv", n_tickers=3, n_days=50, seed=7)
    assert a.read_bytes() == b.read_bytes()


def test_shape_and_contract(tmp_path: Path) -> None:
    path = write_synthetic_prices(tmp_path / "s.csv", n_tickers=4, n_days=25, seed=1)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 100
    assert len({(r["ticker"], r["date"]) for r in rows}) == 100
    assert all(float(r["close"]) > 0 for r in rows)
    assert all(r["ticker"].startswith("SYN") for r in rows)
    assert load_prices(path, tmp_path / "s.duckdb") == 100


def test_dates_skip_weekends(tmp_path: Path) -> None:
    path = write_synthetic_prices(tmp_path / "s.csv", n_tickers=1, n_days=10, seed=1)
    with path.open(newline="") as handle:
        dates = [r["date"] for r in csv.DictReader(handle)]
    assert all(date.fromisoformat(d).weekday() < 5 for d in dates)
