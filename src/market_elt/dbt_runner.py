"""Run dbt in a subprocess and summarize its ``run_results.json``.

dbt keeps global state per process, so each invocation gets its own
subprocess and its own target path. The summary is read from the artifact
dbt writes, not scraped from the console.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from market_elt import config

PROJECT_DIR: Final = config.ROOT / "transform"

_PASS: Final = frozenset({"success", "pass"})
_FAIL: Final = frozenset({"fail", "error", "runtime error"})
_WARN: Final = frozenset({"warn"})
_SKIP: Final = frozenset({"skipped", "no-op"})

RunStatus = Literal["success", "error", "empty"]


@dataclass(frozen=True)
class DbtSummary:
    """Node counts from one dbt invocation."""

    status: RunStatus
    n_pass: int
    n_fail: int
    n_warn: int
    n_skip: int
    failed_nodes: tuple[str, ...]


@dataclass(frozen=True)
class DbtRun:
    """A finished dbt subprocess and the summary of its artifact."""

    returncode: int
    stdout: str
    summary: DbtSummary


def _node_name(unique_id: str) -> str:
    parts = unique_id.split(".")
    if parts[0] == "unit_test":
        return parts[-1]
    return parts[2] if len(parts) > 2 else unique_id


def parse_run_results(path: Path) -> DbtSummary:
    """Summarize a dbt ``run_results.json``.

    Raises ``ValueError`` on a node status this parser does not know, so a
    new dbt status can never be counted as a pass by omission.
    """
    results = json.loads(path.read_text())["results"]
    counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    failed: list[str] = []
    for node in results:
        status = node["status"]
        if status in _PASS:
            counts["pass"] += 1
        elif status in _FAIL:
            counts["fail"] += 1
            failed.append(_node_name(node["unique_id"]))
        elif status in _WARN:
            counts["warn"] += 1
        elif status in _SKIP:
            counts["skip"] += 1
        else:
            raise ValueError(f"unknown dbt node status {status!r} in {path}")
    overall: RunStatus = "empty" if not results else "error" if failed else "success"
    return DbtSummary(
        status=overall,
        n_pass=counts["pass"],
        n_fail=counts["fail"],
        n_warn=counts["warn"],
        n_skip=counts["skip"],
        failed_nodes=tuple(failed),
    )


def run_dbt(
    command: str,
    db_path: Path,
    target_path: Path,
    extra_args: tuple[str, ...] = (),
) -> DbtRun:
    """Run ``dbt <command>`` against ``db_path`` and summarize the result."""
    args = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        command,
        "--project-dir",
        str(PROJECT_DIR),
        "--profiles-dir",
        str(PROJECT_DIR),
        "--target-path",
        str(target_path),
        *extra_args,
    ]
    run_results = target_path / "run_results.json"
    run_results.unlink(missing_ok=True)
    result = subprocess.run(
        args,
        env={**os.environ, "MARKET_ELT_DB": str(db_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    if not run_results.exists():
        raise RuntimeError(f"dbt {command} wrote no run_results.json:\n{result.stdout}")
    return DbtRun(
        returncode=result.returncode,
        stdout=result.stdout,
        summary=parse_run_results(run_results),
    )
