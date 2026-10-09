"""The dbt unit test for daily_metrics must match the independent reference script."""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import Any

import yaml

from market_elt import config

MARTS_YML = config.ROOT / "transform" / "models" / "marts" / "_marts.yml"
REFERENCE = config.ROOT / "scripts" / "daily_metrics_reference.py"


def _load_reference() -> ModuleType:
    spec = importlib.util.spec_from_file_location("daily_metrics_reference", REFERENCE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _unit_test() -> dict[str, Any]:
    tests = yaml.safe_load(MARTS_YML.read_text())["unit_tests"]
    (unit_test,) = (t for t in tests if t["name"] == "daily_metrics_matches_reference")
    return dict(unit_test)


def test_given_rows_are_the_reference_input() -> None:
    reference = _load_reference()
    (given,) = _unit_test()["given"]
    rows = tuple((r["price_date"], r["ticker"], r["close"]) for r in given["rows"])
    assert rows == reference.INPUT_ROWS


def test_expected_rows_are_the_reference_output() -> None:
    reference = _load_reference()
    expected = _unit_test()["expect"]["rows"]
    assert expected == reference.reference_metrics(reference.INPUT_ROWS)
