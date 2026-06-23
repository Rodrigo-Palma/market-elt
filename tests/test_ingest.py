"""Tests for the EL (load) step."""

from __future__ import annotations

from pathlib import Path

import duckdb

from market_elt import config
from market_elt.ingest import load_prices


def test_load_prices_row_count(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    rows = load_prices(config.SAMPLE_CSV, db)
    assert rows == 15


def test_loaded_table_has_expected_tickers(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    con = duckdb.connect(str(db))
    try:
        tickers = {
            row[0] for row in con.execute("SELECT DISTINCT ticker FROM raw.prices").fetchall()
        }
    finally:
        con.close()
    assert tickers == {"PETR4", "VALE3", "ITUB4"}
