"""Tests for parsing dbt's run_results.json into a run summary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from market_elt.dbt_runner import DbtSummary, parse_run_results, run_dbt


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
        ],
    )

    summary = parse_run_results(path)

    assert (summary.n_pass, summary.n_fail, summary.n_warn, summary.n_skip) == (2, 2, 1, 1)
    assert summary.status == "error"
    assert summary.failed_nodes == ("unique_daily_metrics_ticker", "daily_metrics")


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
