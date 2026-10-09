"""Smoke test for benchmarks/scale.py at a tiny size."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

from market_elt import config


def test_scale_benchmark_writes_one_row_per_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location("scale", config.ROOT / "benchmarks" / "scale.py")
    assert spec is not None
    assert spec.loader is not None
    scale = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scale", scale)  # dataclasses look the module up
    spec.loader.exec_module(scale)

    scale.main(["--sizes", "500", "--repeats", "1", "--out", str(tmp_path)])

    with (tmp_path / "results.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [int(r["rows"]) for r in rows] == [500]
    assert int(rows[0]["dbt_nodes_passed"]) > 0
    assert "Median of 1 runs" in (tmp_path / "results.md").read_text()
