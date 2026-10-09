"""Mutation check: break each guarantee on purpose and watch its test go red.

Every mutation is one exact text replacement in one file. The script copies
the repo to a temporary directory, checks that the target tests pass on the
unmutated copy, then applies each mutation alone, runs the target tests and
requires them to fail with the expected text in the output. The working tree
is never touched.

Run: uv run python scripts/mutations.py   (or: make mutate)
Exit code 0 only when every mutation was caught.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
COPY_IGNORE: Final = shutil.ignore_patterns(
    ".git",
    ".venv",
    "target",
    "logs",
    "*.duckdb",
    "*.duckdb.wal",
    "__pycache__",
    ".*_cache",
    "site",
)


@dataclass(frozen=True)
class Mutation:
    name: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    expect: str


MUTATIONS: Final[tuple[Mutation, ...]] = (
    Mutation(
        name="drop the (ticker, price_date) uniqueness test",
        path="transform/models/staging/_staging.yml",
        old="    data_tests:\n      - unique_combination_of_columns:\n"
        "          arguments:\n            combination_of_columns: [ticker, price_date]\n"
        "    columns:\n      - name: price_date",
        new="    columns:\n      - name: price_date",
        tests=("tests/test_quality_gates.py::test_dbt_build_fails_on_the_expected_gate",),
        expect="duplicate_key.csv",
    ),
    Mutation(
        name="no NaN rule in price_reject_reason",
        path="transform/macros/price_reject_reason.sql",
        old="        when isnan({{ close }}) then 'nan_close'\n",
        new="",
        tests=("tests/test_quality_gates.py", "-k", "nan_close"),
        expect="nan_close",
    ),
    Mutation(
        name="no blank-ticker rule in price_reject_reason",
        path="transform/macros/price_reject_reason.sql",
        old="        when nullif(trim({{ ticker }}), '') is null then 'blank_ticker'\n",
        new="",
        tests=("tests/test_quality_gates.py", "-k", "blank_ticker"),
        expect="blank_ticker",
    ),
    Mutation(
        name="stg_prices_rejected silently drops null closes",
        path="transform/models/staging/stg_prices_rejected.sql",
        old="where {{ price_reject_reason('ticker', 'close') }} is not null",
        new="where {{ price_reject_reason('ticker', 'close') }} is not null and close is not null",
        tests=(
            "tests/test_quality_gates.py::test_every_raw_row_lands_in_exactly_one_staging_model",
        ),
        expect="assert_staging_reconciles_with_raw",
    ),
    Mutation(
        name="sqrt(365) instead of sqrt(252)",
        path="transform/models/marts/daily_metrics.sql",
        old="* sqrt(252)",
        new="* sqrt(365)",
        tests=("tests/test_transform.py",),
        expect="daily_metrics_matches_reference",
    ),
    Mutation(
        name="centered window (10 preceding and 9 following)",
        path="transform/models/marts/features_daily.sql",
        old="rows between 19 preceding and current row",
        new="rows between 10 preceding and 9 following",
        tests=("tests/test_features_causal.py",),
        expect="test_features_up_to_t_ignore_rows_after_t",
    ),
    Mutation(
        name="observations cast to integer against a bigint contract",
        path="transform/models/marts/daily_metrics.sql",
        old="    count(*)                                            as observations,",
        new="    cast(count(*) as integer)                           as observations,",
        tests=("tests/test_transform.py",),
        expect="contract",
    ),
    Mutation(
        name="recency gate ignores its threshold",
        path="transform/tests/generic/max_date_at_most_days_old.sql",
        old="{{ reference }} - {{ max_age_days }}::integer",
        new="{{ reference }} - ({{ max_age_days }} + 100000)::integer",
        tests=(
            "tests/test_quality_gates.py::test_price_recency_gate_measures_the_data_not_the_load",
        ),
        expect="FAILED tests/test_quality_gates.py::test_price_recency_gate",
    ),
    Mutation(
        name="dbt exit code ignored",
        path="src/market_elt/pipeline.py",
        old='    if dbt.returncode != 0 and dbt.summary.status == "success":',
        new="    if False:",
        tests=("tests/test_pipeline.py::test_nonzero_dbt_exit_is_not_a_success",),
        expect="nonzero_exit",
    ),
)


def _pytest(workdir: Path, tests: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(workdir / "src")}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-cov", "-p", "no:cacheprovider", *tests],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _check_copy_imports_itself(workdir: Path) -> None:
    """An editable install would otherwise import the repo, not the mutated copy."""
    probe = subprocess.run(
        [sys.executable, "-c", "import market_elt.config as c; print(c.ROOT)"],
        cwd=workdir,
        env={**os.environ, "PYTHONPATH": str(workdir / "src")},
        capture_output=True,
        text=True,
        check=True,
    )
    imported = Path(probe.stdout.strip()).resolve()
    if imported != workdir.resolve():
        raise SystemExit(f"the copy imports market_elt from {imported}, not {workdir}")


def _apply(workdir: Path, mutation: Mutation) -> str:
    path = workdir / mutation.path
    original = path.read_text()
    if original.count(mutation.old) != 1:
        raise SystemExit(f"{mutation.name}: the text to replace is not unique in {mutation.path}")
    path.write_text(original.replace(mutation.old, mutation.new))
    return original


def run_mutation(workdir: Path, mutation: Mutation) -> bool:
    """True when the target tests pass unmutated and fail mutated, as expected."""
    baseline = _pytest(workdir, mutation.tests)
    if baseline.returncode != 0:
        print(f"BASELINE RED  {mutation.name}\n{baseline.stdout[-2000:]}")
        return False
    original = _apply(workdir, mutation)
    started = time.perf_counter()
    try:
        mutated = _pytest(workdir, mutation.tests)
    finally:
        (workdir / mutation.path).write_text(original)
    elapsed = time.perf_counter() - started
    output = mutated.stdout + mutated.stderr
    caught = mutated.returncode != 0 and mutation.expect in output
    verdict = "CAUGHT  " if caught else "SURVIVED"
    print(f"{verdict} {mutation.name}  [{mutated.returncode=}, {elapsed:.1f}s]", flush=True)
    if not caught:
        print(output[-2000:])
    return caught


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="market-elt-mutations-") as tmp:
        workdir = Path(tmp) / "repo"
        shutil.copytree(ROOT, workdir, ignore=COPY_IGNORE)
        _check_copy_imports_itself(workdir)
        results = [run_mutation(workdir, mutation) for mutation in MUTATIONS]
    print(f"{sum(results)} of {len(results)} mutations caught")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
