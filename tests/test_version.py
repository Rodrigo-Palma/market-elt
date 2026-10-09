"""The package version has a single source of truth: the installed metadata."""

from __future__ import annotations

import tomllib
from importlib.metadata import version

import market_elt
from market_elt import config


def test_version_matches_pyproject_and_metadata() -> None:
    pyproject = tomllib.loads((config.ROOT / "pyproject.toml").read_text())
    assert market_elt.__version__ == pyproject["project"]["version"]
    assert market_elt.__version__ == version("market-elt")


def test_version_is_not_hardcoded() -> None:
    source = (config.ROOT / "src" / "market_elt" / "__init__.py").read_text()
    assert '__version__ = "' not in source
