"""Security hardening that lives in config files and must not regress."""

from __future__ import annotations

import re
import tomllib
from typing import Any

import yaml

from market_elt import config

CHECKOUT = "actions/checkout@"
WORKFLOWS = sorted((config.ROOT / ".github" / "workflows").glob("*.yml"))

# First patched release of each locked package with a published advisory.
MIN_PATCHED = {
    "sqlparse": (0, 6, 0),  # GHSA-f2ff-p2ww-7p4p, GHSA-prg7-hcfm-mfcr, GHSA-pwgv-4x5q-6m9f
    "urllib3": (2, 8, 0),  # GHSA-8988-9cw3-xx77, GHSA-vxq7-64xx-v4gw
    "virtualenv": (21, 7, 13),  # GHSA-p58f-9548-mpm2, GHSA-94p9-xgh2-xp45
}

# The only paths the runtime user may write to: the database and dbt's
# target and log directories.
WRITABLE_PATHS = {"/app/out", "/app/transform/target", "/app/transform/logs"}


def _checkout_steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for workflow in WORKFLOWS:
        jobs = yaml.safe_load(workflow.read_text())["jobs"]
        for job in jobs.values():
            job_steps = job.get("steps", [])
            steps += [s for s in job_steps if str(s.get("uses", "")).startswith(CHECKOUT)]
    return steps


def test_every_checkout_drops_the_token_from_git_config() -> None:
    steps = _checkout_steps()
    assert steps, "no actions/checkout step found"
    for step in steps:
        assert step.get("with", {}).get("persist-credentials") is False, step


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def test_locked_versions_are_past_the_known_advisories() -> None:
    lock = tomllib.loads((config.ROOT / "uv.lock").read_text())
    locked = {p["name"]: p["version"] for p in lock["package"]}
    for name, floor in MIN_PATCHED.items():
        assert _version(locked[name]) >= floor, f"{name} {locked[name]} is below {floor}"


def _runtime_stage() -> list[str]:
    text = (config.ROOT / "Dockerfile").read_text()
    stages = re.split(r"^FROM ", text, flags=re.MULTILINE)
    return [line.strip() for line in stages[-1].splitlines() if line.strip()]


def test_runtime_user_cannot_rewrite_code_or_venv() -> None:
    copies = [line for line in _runtime_stage() if line.startswith("COPY")]
    assert copies, "runtime stage has no COPY"
    for line in copies:
        assert "--chown" not in line, line


def test_runtime_user_owns_only_the_writable_paths() -> None:
    chowns = [line for line in _runtime_stage() if "chown" in line]
    owned = {path for line in chowns for path in re.findall(r"/app\S*", line)}
    assert owned == WRITABLE_PATHS
