"""Negative tests: each quality gate is shown failing on the bad input it exists for.

A gate that has never been seen failing is not a gate. Every case loads a
deliberately broken file into an isolated DuckDB, runs ``dbt build`` and
asserts that the build fails on the expected node, read from run_results.json.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from market_elt.dbt_runner import DbtRun, run_dbt
from market_elt.ingest import ContractViolationError, load_prices

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_CSV = Path(__file__).parents[1] / "data" / "sample" / "prices.csv"
REJECTED_GATE = "row_count_at_most_stg_prices_rejected__var_max_rejected_rows_"


def _build(csv: str | Path, tmp_path: Path, *extra_args: str) -> tuple[DbtRun, Path]:
    db = tmp_path / "gate.duckdb"
    load_prices(FIXTURES / csv, db)
    return run_dbt("build", db, tmp_path / "target", extra_args), db


def _rejected_reasons(db: Path) -> list[str]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute("SELECT reject_reason FROM stg_prices_rejected").fetchall()
    finally:
        con.close()
    return [row[0] for row in rows]


@pytest.mark.parametrize(
    ("fixture", "failing_gate"),
    [
        ("duplicate_key.csv", "unique_combination_of_columns_stg_prices_ticker__price_date"),
        ("null_close.csv", REJECTED_GATE),
        ("negative_close.csv", REJECTED_GATE),
        ("nan_close.csv", REJECTED_GATE),
        ("inf_close.csv", REJECTED_GATE),
        ("blank_ticker.csv", REJECTED_GATE),
        ("null_ticker.csv", "source_not_null_raw_prices_ticker"),
    ],
)
def test_dbt_build_fails_on_the_expected_gate(
    tmp_path: Path, fixture: str, failing_gate: str
) -> None:
    run, _ = _build(fixture, tmp_path)

    assert run.returncode != 0
    assert run.summary.status == "error"
    assert failing_gate in run.summary.failed_nodes


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("null_close.csv", "null_close"),
        ("negative_close.csv", "non_positive_close"),
        ("nan_close.csv", "nan_close"),
        ("inf_close.csv", "infinite_close"),
        ("blank_ticker.csv", "blank_ticker"),
    ],
)
def test_rejected_rows_are_kept_with_their_reason(
    tmp_path: Path, fixture: str, reason: str
) -> None:
    _, db = _build(fixture, tmp_path)
    assert _rejected_reasons(db) == [reason]


def test_raising_the_tolerance_quarantines_instead_of_failing(tmp_path: Path) -> None:
    run, db = _build("null_close.csv", tmp_path, "--vars", "{max_rejected_rows: 1}")

    assert run.returncode == 0, run.stdout
    assert _rejected_reasons(db) == ["null_close"]


def _count(db: Path, relation: str) -> int:
    con = duckdb.connect(str(db), read_only=True)
    try:
        row = con.execute(f"SELECT count(*) FROM {relation}").fetchone()
    finally:
        con.close()
    return int(row[0]) if row else 0


def test_every_raw_row_lands_in_exactly_one_staging_model(tmp_path: Path) -> None:
    run, db = _build("mixed_bad_rows.csv", tmp_path, "--vars", "{max_rejected_rows: 6}")

    assert run.returncode == 0, run.stdout
    n_raw, n_valid, n_rejected = (
        _count(db, name) for name in ("raw.prices", "stg_prices", "stg_prices_rejected")
    )
    assert (n_raw, n_valid, n_rejected) == (9, 3, 6)
    assert sorted(_rejected_reasons(db)) == [
        "blank_ticker",
        "infinite_close",
        "infinite_close",
        "nan_close",
        "non_positive_close",
        "null_close",
    ]
    assert "assert_staging_reconciles_with_raw" not in run.summary.failed_nodes


def test_type_violation_never_reaches_dbt(tmp_path: Path) -> None:
    with pytest.raises(ContractViolationError, match="close"):
        load_prices(FIXTURES / "bad_type.csv", tmp_path / "gate.duckdb")


RECENCY_GATE = (
    "max_date_at_most_days_old_stg_prices__var_as_of_date___price_date___var_max_price_age_days_"
)


@pytest.mark.parametrize(
    ("dbt_vars", "fails"),
    [
        # The sample ends on 2026-06-05.
        ('{"max_price_age_days": 3, "as_of_date": "2026-06-07"}', False),
        ('{"max_price_age_days": 3, "as_of_date": "2026-06-09"}', True),
        # A file loaded just now whose prices are months old: source
        # freshness passes it, the recency gate does not.
        ('{"max_price_age_days": 5}', True),
    ],
)
def test_price_recency_gate_measures_the_data_not_the_load(
    tmp_path: Path, dbt_vars: str, fails: bool
) -> None:
    db = tmp_path / "gate.duckdb"
    load_prices(SAMPLE_CSV, db)

    run = run_dbt("build", db, tmp_path / "target", ("--vars", dbt_vars))

    assert (run.returncode != 0) is fails
    assert (RECENCY_GATE in run.summary.failed_nodes) is fails
    assert run.summary.n_fail == int(fails)


def test_price_recency_gate_is_off_by_default(tmp_path: Path) -> None:
    run, _ = _build(SAMPLE_CSV, tmp_path)

    assert run.returncode == 0, run.stdout
    assert RECENCY_GATE not in run.summary.failed_nodes


@pytest.mark.parametrize(("age_hours", "fails"), [(1, False), (96, True)])
def test_source_freshness_errors_on_a_stale_load(
    tmp_path: Path, age_hours: int, fails: bool
) -> None:
    db = tmp_path / "gate.duckdb"
    load_prices(SAMPLE_CSV, db)
    con = duckdb.connect(str(db))
    try:
        con.execute(f"UPDATE raw.prices SET loaded_at = now() - INTERVAL {age_hours} HOUR")
    finally:
        con.close()

    run = run_dbt("source freshness", db, tmp_path / "target")

    assert (run.returncode != 0) is fails
    assert ("raw.prices" in run.summary.failed_nodes) is fails
