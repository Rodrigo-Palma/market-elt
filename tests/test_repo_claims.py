"""Numbers and versions written in docs and config must match what runs."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib

import yaml

from market_elt import config


def _collected_test_count() -> int:
    result = subprocess.run(
        # addopts already holds -q, so the last line is "N tests collected".
        [sys.executable, "-m", "pytest", "--collect-only", "--no-cov", "-p", "no:cacheprovider"],
        cwd=config.ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    match = re.search(r"^(\d+) tests? collected", result.stdout, re.MULTILINE)
    assert match, result.stdout[-2000:]
    return int(match.group(1))


def test_readme_test_count_matches_the_collected_suite() -> None:
    readme = (config.ROOT / "README.md").read_text()
    match = re.search(r"^(\d+) pytest tests,", readme, re.MULTILINE)
    assert match, "README.md lost its test count line"
    assert int(match.group(1)) == _collected_test_count()


def _locked_version(name: str) -> str:
    lock = tomllib.loads((config.ROOT / "uv.lock").read_text())
    (package,) = [p for p in lock["package"] if p["name"] == name]
    return str(package["version"])


def test_pre_commit_ruff_hook_matches_the_locked_ruff() -> None:
    hooks = yaml.safe_load((config.ROOT / ".pre-commit-config.yaml").read_text())
    (ruff_repo,) = [r for r in hooks["repos"] if r["repo"].endswith("/ruff-pre-commit")]
    assert ruff_repo["rev"] == f"v{_locked_version('ruff')}"
