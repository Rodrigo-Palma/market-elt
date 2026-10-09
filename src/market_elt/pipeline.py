"""One idempotent pipeline run: load, dbt build, and a row in meta.pipeline_runs.

Re-running is safe: the load replaces ``raw.prices`` and dbt rebuilds every
model, so only ``meta.pipeline_runs`` grows, by exactly one row per run.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import duckdb

from market_elt.dbt_runner import DbtSummary, run_dbt
from market_elt.ingest import ContractViolationError, load_prices
from market_elt.logs import get_logger

RUNS_DDL: Final = """
CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
    run_id        VARCHAR PRIMARY KEY,
    started_at    TIMESTAMPTZ NOT NULL,
    finished_at   TIMESTAMPTZ NOT NULL,
    source_file   VARCHAR NOT NULL,
    rows_loaded   BIGINT NOT NULL,
    rows_rejected BIGINT,
    dbt_status    VARCHAR NOT NULL,
    n_pass        INTEGER NOT NULL,
    n_fail        INTEGER NOT NULL,
    n_warn        INTEGER NOT NULL,
    n_skip        INTEGER NOT NULL,
    failed_nodes  VARCHAR[] NOT NULL
)
"""

LOAD_FAILED: Final = "load_failed"


@dataclass(frozen=True)
class PipelineRun:
    """The record written to ``meta.pipeline_runs`` for one run."""

    run_id: str
    started_at: datetime
    finished_at: datetime
    source_file: str
    rows_loaded: int
    rows_rejected: int | None
    dbt_status: str
    n_pass: int
    n_fail: int
    n_warn: int
    n_skip: int
    failed_nodes: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        return self.dbt_status == "success"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _count_rejected(db_path: Path) -> int | None:
    con = duckdb.connect(str(db_path))
    try:
        exists = con.execute(
            "SELECT count(*) FROM information_schema.tables"
            " WHERE table_name = 'stg_prices_rejected'"
        ).fetchone()
        if not exists or exists[0] == 0:
            return None
        row = con.execute("SELECT count(*) FROM stg_prices_rejected").fetchone()
        return int(row[0]) if row else None
    finally:
        con.close()


def record_run(db_path: Path, run: PipelineRun) -> None:
    """Append ``run`` to ``meta.pipeline_runs``."""
    record = asdict(run)
    record["failed_nodes"] = list(run.failed_nodes)
    columns = ", ".join(record)
    placeholders = ", ".join(f"${name}" for name in record)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS meta")
        con.execute(RUNS_DDL)
        con.execute(f"INSERT INTO meta.pipeline_runs ({columns}) VALUES ({placeholders})", record)
    finally:
        con.close()


def run_pipeline(
    csv_path: Path,
    db_path: Path,
    target_path: Path,
    dbt_args: tuple[str, ...] = (),
) -> PipelineRun:
    """Load ``csv_path``, run ``dbt build`` and record the run.

    A contract violation at load time is recorded as ``load_failed`` and
    re-raised; a failing dbt node is recorded and returned.
    """
    log = get_logger()
    started = PipelineRun(
        run_id=uuid.uuid4().hex,
        started_at=_now(),
        finished_at=_now(),
        source_file=str(csv_path),
        rows_loaded=0,
        rows_rejected=None,
        dbt_status=LOAD_FAILED,
        n_pass=0,
        n_fail=0,
        n_warn=0,
        n_skip=0,
        failed_nodes=(),
    )
    log.info("run.started", extra={"fields": {"run_id": started.run_id, "source": str(csv_path)}})
    try:
        rows_loaded = load_prices(csv_path, db_path)
    except ContractViolationError as exc:
        failed = replace(started, finished_at=_now())
        record_run(db_path, failed)
        log.error("load.failed", extra={"fields": {"run_id": started.run_id, "error": str(exc)}})
        raise
    log.info("load.done", extra={"fields": {"run_id": started.run_id, "rows": rows_loaded}})

    summary: DbtSummary = run_dbt("build", db_path, target_path, dbt_args).summary
    run = replace(
        started,
        finished_at=_now(),
        rows_loaded=rows_loaded,
        rows_rejected=_count_rejected(db_path),
        dbt_status=summary.status,
        n_pass=summary.n_pass,
        n_fail=summary.n_fail,
        n_warn=summary.n_warn,
        n_skip=summary.n_skip,
        failed_nodes=summary.failed_nodes,
    )
    record_run(db_path, run)
    fields = asdict(run)
    log.log(
        logging.INFO if run.succeeded else logging.ERROR, "run.finished", extra={"fields": fields}
    )
    return run
