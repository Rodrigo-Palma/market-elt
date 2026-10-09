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
REJECTED_GATE = "row_count_at_most_stg_prices_rejected__var_max_rejected_rows_"


def _build(csv_name: str, tmp_path: Path, *extra_args: str) -> tuple[DbtRun, Path]:
    db = tmp_path / "gate.duckdb"
    load_prices(FIXTURES / csv_name, db)
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
    [("null_close.csv", "null_close"), ("negative_close.csv", "non_positive_close")],
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


def test_type_violation_never_reaches_dbt(tmp_path: Path) -> None:
    with pytest.raises(ContractViolationError, match="close"):
        load_prices(FIXTURES / "bad_type.csv", tmp_path / "gate.duckdb")
