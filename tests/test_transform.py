"""Tests for the T (dbt transform) step: EL -> dbt build -> assert marts."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from market_elt import config
from market_elt.dbt_runner import run_dbt
from market_elt.ingest import load_prices

EXPECTED_TICKERS = {"PETR4", "VALE3", "ITUB4"}
OBSERVATIONS_PER_TICKER = 5


@pytest.fixture(scope="module")
def transformed_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run the full pipeline (load + dbt build) against an isolated DuckDB."""
    workdir = tmp_path_factory.mktemp("transform")
    db = workdir / "test.duckdb"
    load_prices(config.SAMPLE_CSV, db)
    run = run_dbt("build", db, workdir / "target")
    assert run.returncode == 0, f"dbt build failed:\n{run.stdout}"
    assert run.summary.status == "success"
    return db


def test_stg_prices_preserves_all_rows(transformed_db: Path) -> None:
    con = duckdb.connect(str(transformed_db), read_only=True)
    try:
        rows = con.execute("SELECT count(*) FROM stg_prices").fetchone()
    finally:
        con.close()
    assert rows is not None
    assert rows[0] == len(EXPECTED_TICKERS) * OBSERVATIONS_PER_TICKER


def test_daily_metrics_one_row_per_ticker(transformed_db: Path) -> None:
    con = duckdb.connect(str(transformed_db), read_only=True)
    try:
        result = con.execute(
            "SELECT ticker, observations FROM daily_metrics ORDER BY ticker"
        ).fetchall()
    finally:
        con.close()
    assert {row[0] for row in result} == EXPECTED_TICKERS
    assert all(row[1] == OBSERVATIONS_PER_TICKER for row in result)


def test_daily_metrics_schema_and_sane_values(transformed_db: Path) -> None:
    con = duckdb.connect(str(transformed_db), read_only=True)
    try:
        columns = {
            row[0]
            for row in con.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'daily_metrics'"
            ).fetchall()
        }
        metrics = con.execute(
            "SELECT last_close, annualized_volatility FROM daily_metrics"
        ).fetchall()
    finally:
        con.close()
    assert columns == {
        "ticker",
        "observations",
        "last_date",
        "last_close",
        "annualized_volatility",
    }
    assert all(last_close > 0 for last_close, _ in metrics)
    assert all(volatility >= 0 for _, volatility in metrics)


def test_every_raw_row_lands_in_exactly_one_staging_model(transformed_db: Path) -> None:
    con = duckdb.connect(str(transformed_db), read_only=True)
    try:
        counts = con.execute(
            "SELECT (SELECT count(*) FROM raw.prices),"
            " (SELECT count(*) FROM stg_prices),"
            " (SELECT count(*) FROM stg_prices_rejected)"
        ).fetchone()
    finally:
        con.close()
    assert counts == (15, 15, 0)
