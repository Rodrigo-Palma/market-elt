"""The package version has a single source of truth: the installed metadata."""

from __future__ import annotations

import re
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


def _released_versions(changelog: str) -> list[str]:
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", changelog, re.MULTILINE)


def test_changelog_latest_release_is_the_package_version() -> None:
    changelog = (config.ROOT / "CHANGELOG.md").read_text()
    released = _released_versions(changelog)
    assert released, "CHANGELOG.md has no dated release section"
    assert released[0] == market_elt.__version__


def test_changelog_releases_have_link_references() -> None:
    changelog = (config.ROOT / "CHANGELOG.md").read_text()
    for release in _released_versions(changelog):
        assert re.search(rf"^\[{re.escape(release)}\]: https://", changelog, re.MULTILINE), release
    assert re.search(r"^\[Unreleased\]: https://.+\.\.\.HEAD$", changelog, re.MULTILINE)


def test_lockfile_records_the_package_version() -> None:
    lock = tomllib.loads((config.ROOT / "uv.lock").read_text())
    (package,) = [p for p in lock["package"] if p["name"] == "market-elt"]
    assert package["version"] == market_elt.__version__
