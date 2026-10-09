"""Tests for the EL (load) step and its input contract."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import duckdb
import pytest

from market_elt import config
from market_elt.ingest import RAW_COLUMNS, ContractViolationError, load_prices

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(db: Path, sql: str) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_load_prices_row_count(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    rows = load_prices(config.SAMPLE_CSV, db)
    assert rows == 15


def test_loaded_table_has_expected_tickers(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    tickers = {row[0] for row in _fetch(db, "SELECT DISTINCT ticker FROM raw.prices")}
    assert tickers == {"PETR4", "VALE3", "ITUB4"}


def test_raw_prices_has_declared_types(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    schema = _fetch(
        db,
        "SELECT column_name, data_type FROM information_schema.columns"
        " WHERE table_schema = 'raw' AND table_name = 'prices' ORDER BY ordinal_position",
    )
    assert dict(schema[: len(RAW_COLUMNS)]) == RAW_COLUMNS
    first = _fetch(db, "SELECT date FROM raw.prices ORDER BY date LIMIT 1")
    assert first == [(dt.date(2026, 6, 1),)]


def test_reload_replaces_instead_of_appending(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    load_prices(config.SAMPLE_CSV, db)
    assert _fetch(db, "SELECT count(*) FROM raw.prices") == [(15,)]


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("bad_header.csv", "header"),
        ("bad_type.csv", "close"),
        ("bad_date.csv", "date"),
    ],
)
def test_contract_violation_fails_the_load(tmp_path: Path, fixture: str, message: str) -> None:
    db = tmp_path / "test.duckdb"
    with pytest.raises(ContractViolationError, match=message):
        load_prices(FIXTURES / fixture, db)


def test_failed_load_keeps_the_previous_good_table(tmp_path: Path) -> None:
    db = tmp_path / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    with pytest.raises(ContractViolationError):
        load_prices(FIXTURES / "bad_type.csv", db)
    assert _fetch(db, "SELECT count(*) FROM raw.prices") == [(15,)]
