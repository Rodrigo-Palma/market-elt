"""Tests for parsing dbt's run_results.json into a run summary."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from market_elt import dbt_runner
from market_elt.dbt_runner import STDERR_TAIL_LINES, DbtSummary, parse_run_results, run_dbt


def _write(tmp_path: Path, results: list[dict[str, str]]) -> Path:
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps({"metadata": {}, "results": results}))
    return path


def _node(unique_id: str, status: str) -> dict[str, str]:
    return {"unique_id": unique_id, "status": status}


def test_counts_pass_fail_warn_and_skip(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            _node("model.market_elt.stg_prices", "success"),
            _node("test.market_elt.not_null_stg_prices_close.abc", "pass"),
            _node("test.market_elt.unique_daily_metrics_ticker.def", "fail"),
            _node("model.market_elt.daily_metrics", "error"),
            _node("test.market_elt.row_count_at_most_x.ghi", "warn"),
            _node("test.market_elt.not_null_daily_metrics_ticker.jkl", "skipped"),
            _node("source.market_elt.raw.prices", "runtime error"),
            _node("unit_test.market_elt.daily_metrics.matches_reference", "pass"),
        ],
    )

    summary = parse_run_results(path)

    assert (summary.n_pass, summary.n_fail, summary.n_warn, summary.n_skip) == (3, 3, 1, 1)
    assert summary.status == "error"
    assert summary.failed_nodes == (
        "unique_daily_metrics_ticker",
        "daily_metrics",
        "raw.prices",
    )


def test_all_green_is_success(tmp_path: Path) -> None:
    path = _write(tmp_path, [_node("model.market_elt.stg_prices", "success")])
    assert parse_run_results(path) == DbtSummary(
        status="success", n_pass=1, n_fail=0, n_warn=0, n_skip=0, failed_nodes=()
    )


def test_empty_results_is_not_success(tmp_path: Path) -> None:
    summary = parse_run_results(_write(tmp_path, []))
    assert summary.status == "empty"


def test_unknown_status_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, [_node("model.market_elt.x", "exploded")])
    with pytest.raises(ValueError, match="exploded"):
        parse_run_results(path)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_run_results(tmp_path / "nope.json")


def test_run_without_artifact_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"no run_results\.json"):
        run_dbt("not-a-dbt-command", tmp_path / "x.duckdb", tmp_path / "target")


def _crash_with(monkeypatch: pytest.MonkeyPatch, stdout: str, stderr: str) -> None:
    """Make dbt exit 2 with the given streams and no artifact."""

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 2, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(dbt_runner.subprocess, "run", fake_run)


def test_crash_message_carries_the_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = "Traceback (most recent call last):\nmashumaro.exceptions.UnserializableField: x\n"
    _crash_with(monkeypatch, stdout="", stderr=stderr)

    with pytest.raises(RuntimeError) as info:
        run_dbt("build", tmp_path / "x.duckdb", tmp_path / "target")

    assert "mashumaro.exceptions.UnserializableField: x" in str(info.value)
    assert "no run_results.json" in str(info.value)


def test_crash_message_keeps_stdout_and_only_the_stderr_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = [f"stderr line {i}" for i in range(STDERR_TAIL_LINES + 10)]
    _crash_with(monkeypatch, stdout="Encountered an error", stderr="\n".join(lines))

    with pytest.raises(RuntimeError) as info:
        run_dbt("build", tmp_path / "x.duckdb", tmp_path / "target")

    message = str(info.value)
    assert "Encountered an error" in message
    assert all(line in message for line in lines[-STDERR_TAIL_LINES:])
    assert "stderr line 9\n" not in message
    assert "10 earlier stderr lines omitted" in message
