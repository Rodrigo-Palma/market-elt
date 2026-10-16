"""The supported Python range is written in four places; all must agree with CI."""

from __future__ import annotations

import sys
import tomllib
from urllib.parse import unquote

import yaml

from market_elt import config

CLASSIFIER_PREFIX = "Programming Language :: Python :: "


def _pyproject() -> dict:
    return tomllib.loads((config.ROOT / "pyproject.toml").read_text())


def _classifier_versions() -> list[str]:
    classifiers = _pyproject()["project"]["classifiers"]
    tails = [c.removeprefix(CLASSIFIER_PREFIX) for c in classifiers if CLASSIFIER_PREFIX in c]
    return sorted((t for t in tails if t.startswith("3.")), key=lambda v: int(v.split(".")[1]))


def _ci_matrix_versions() -> list[str]:
    workflow = yaml.safe_load((config.ROOT / ".github" / "workflows" / "ci.yml").read_text())
    matrix = workflow["jobs"]["quality"]["strategy"]["matrix"]["python-version"]
    return [str(v) for v in matrix]


def test_ci_tests_every_classified_version() -> None:
    assert _classifier_versions() == ["3.12", "3.13", "3.14"]
    assert _ci_matrix_versions() == _classifier_versions()


def test_requires_python_stops_after_the_last_tested_version() -> None:
    versions = _classifier_versions()
    last_minor = int(versions[-1].split(".")[1])
    expected = f">={versions[0]},<3.{last_minor + 1}"
    assert _pyproject()["project"]["requires-python"] == expected


def test_readme_badge_lists_the_tested_versions() -> None:
    readme = unquote((config.ROOT / "README.md").read_text())
    assert f"python-{' | '.join(_classifier_versions())}-blue" in readme
    assert "python-3.12+" not in readme


def test_running_interpreter_is_in_the_supported_range() -> None:
    assert f"{sys.version_info.major}.{sys.version_info.minor}" in _classifier_versions()


def test_python_314_requires_a_mashumaro_that_imports_on_it() -> None:
    # mashumaro <3.17 raises UnserializableField at import on 3.14, which kills dbt.
    assert "mashumaro>=3.17" in _pyproject()["project"]["dependencies"]
