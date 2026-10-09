"""End-to-end tests for ``market-elt run``: load, dbt build and the run log."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb
import pytest

from market_elt import config
from market_elt.cli import main
from market_elt.ingest import ContractViolationError
from market_elt.logs import JsonFormatter
from market_elt.pipeline import run_pipeline

FIXTURES = Path(__file__).parent / "fixtures"


def _fetch(db: Path, sql: str) -> list[tuple[object, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_two_runs_are_idempotent_and_both_recorded(tmp_path: Path) -> None:
    db = tmp_path / "pipe.duckdb"
    first = run_pipeline(config.SAMPLE_CSV, db, tmp_path / "target")
    counts_after_first = _fetch(
        db, "SELECT (SELECT count(*) FROM raw.prices), (SELECT count(*) FROM daily_metrics)"
    )
    metrics_after_first = _fetch(db, "SELECT * FROM daily_metrics ORDER BY ticker")

    second = run_pipeline(config.SAMPLE_CSV, db, tmp_path / "target")

    assert first.run_id != second.run_id
    assert counts_after_first == [(15, 3)]
    assert _fetch(
        db, "SELECT (SELECT count(*) FROM raw.prices), (SELECT count(*) FROM daily_metrics)"
    ) == [(15, 3)]
    assert _fetch(db, "SELECT * FROM daily_metrics ORDER BY ticker") == metrics_after_first
    runs = _fetch(
        db,
        "SELECT rows_loaded, rows_rejected, dbt_status, n_fail, finished_at >= started_at"
        " FROM meta.pipeline_runs ORDER BY started_at",
    )
    assert runs == [(15, 0, "success", 0, True), (15, 0, "success", 0, True)]
    assert second.n_pass == first.n_pass > 0


def test_failed_gate_is_recorded_with_the_rejected_count(tmp_path: Path) -> None:
    db = tmp_path / "pipe.duckdb"
    run = run_pipeline(FIXTURES / "null_close.csv", db, tmp_path / "target")

    assert run.dbt_status == "error"
    assert run.rows_rejected == 1
    assert _fetch(db, "SELECT dbt_status, rows_loaded, rows_rejected FROM meta.pipeline_runs") == [
        ("error", 3, 1)
    ]


def test_contract_violation_is_recorded_then_raised(tmp_path: Path) -> None:
    db = tmp_path / "pipe.duckdb"
    with pytest.raises(ContractViolationError):
        run_pipeline(FIXTURES / "bad_type.csv", db, tmp_path / "target")
    assert _fetch(db, "SELECT dbt_status, rows_loaded, n_pass FROM meta.pipeline_runs") == [
        ("load_failed", 0, 0)
    ]


def test_cli_exit_code_follows_the_run(tmp_path: Path) -> None:
    common = ["--db", str(tmp_path / "cli.duckdb"), "--target-path", str(tmp_path / "t")]
    assert main(["run", "--csv", str(FIXTURES / "bad_header.csv"), *common]) == 1
    assert main(["run", "--csv", str(FIXTURES / "null_close.csv"), *common]) == 1
    tolerant = ["--max-rejected-rows", "1"]
    assert main(["run", "--csv", str(FIXTURES / "null_close.csv"), *common, *tolerant]) == 0


def test_cli_load_only(tmp_path: Path) -> None:
    db = tmp_path / "cli.duckdb"
    assert main(["load", "--db", str(db)]) == 0
    assert _fetch(db, "SELECT count(*) FROM raw.prices") == [(15,)]


def test_json_formatter_emits_one_parseable_object() -> None:
    record = logging.LogRecord("market_elt", logging.INFO, __file__, 1, "dbt.done", None, None)
    record.fields = {"n_pass": 17, "status": "success"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "dbt.done"
    assert payload["level"] == "INFO"
    assert payload["n_pass"] == 17
    assert "ts" in payload
