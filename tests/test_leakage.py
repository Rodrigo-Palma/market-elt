"""Tests for benchmarks/leakage.py: the Wilson interval and the leak it measures."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from market_elt import config


@pytest.fixture(scope="module")
def leakage() -> ModuleType:
    path = config.ROOT / "benchmarks" / "leakage.py"
    spec = importlib.util.spec_from_file_location("leakage", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["leakage"] = module  # dataclasses look the module up
    spec.loader.exec_module(module)
    return module


def test_wilson_matches_a_known_interval(leakage: ModuleType) -> None:
    # 50 of 100: the textbook Wilson interval is 0.4038 to 0.5962.
    low, high = leakage.wilson(50, 100)
    assert (round(low, 4), round(high, 4)) == (0.4038, 0.5962)


def test_wilson_stays_inside_zero_one_at_the_edges(leakage: ModuleType) -> None:
    low, high = leakage.wilson(0, 10)
    assert low == pytest.approx(0.0, abs=1e-12)
    assert 0 < high < 1
    with pytest.raises(ValueError):
        leakage.wilson(0, 0)


def test_leaky_window_beats_point_in_time_on_a_random_walk(
    leakage: ModuleType, tmp_path: Path
) -> None:
    out = tmp_path / "leakage.md"
    scores = {
        s.feature: s for s in leakage.main(["--tickers", "60", "--days", "400", "--out", str(out)])
    }
    honest, leaky = scores["point_in_time"], scores["leaky"]
    # No signal exists by construction: the honest rule's interval covers 50%.
    assert honest.test_low <= 0.5 <= honest.test_high
    # The centered window reads the label, so it clears 50% by a wide margin.
    assert leaky.test_low > honest.test_high
    assert leaky.test_low > 0.53
    assert "| leaky |" in out.read_text()
