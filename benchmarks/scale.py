"""Scale benchmark on SYNTHETIC data: load + dbt build at growing row counts.

For each size, writes deterministic synthetic prices (market_elt.synthetic,
seed fixed), loads them into a fresh DuckDB and runs the full ``dbt build``
(models, contracts, data tests and unit tests). Reports the median of
``--repeats`` runs, plus dbt's own execution time from run_results.json,
which excludes dbt's start-up cost.

Run: uv run python benchmarks/scale.py
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Final

from market_elt.dbt_runner import run_dbt
from market_elt.ingest import load_prices
from market_elt.synthetic import write_synthetic_prices

SEED: Final = 20260101
DAYS: Final = 1000
DEFAULT_SIZES: Final = (10_000, 100_000, 1_000_000)
OUT_DIR: Final = Path(__file__).parent


@dataclass(frozen=True)
class Measurement:
    rows: int
    tickers: int
    days: int
    load_s: float
    dbt_build_wall_s: float
    dbt_build_exec_s: float
    dbt_nodes_passed: int


def _timed_run(csv_path: Path, workdir: Path) -> tuple[float, float, float, int]:
    db = workdir / "bench.duckdb"
    db.unlink(missing_ok=True)
    start = time.perf_counter()
    load_prices(csv_path, db)
    load_s = time.perf_counter() - start
    start = time.perf_counter()
    run = run_dbt("build", db, workdir / "target")
    wall_s = time.perf_counter() - start
    if run.summary.status != "success":
        raise RuntimeError(f"dbt build failed:\n{run.stdout}")
    exec_s = json.loads((workdir / "target" / "run_results.json").read_text())["elapsed_time"]
    return load_s, wall_s, float(exec_s), run.summary.n_pass


def measure(rows: int, repeats: int, workdir: Path) -> Measurement:
    tickers = max(1, rows // DAYS)
    days = rows // tickers
    csv_path = write_synthetic_prices(workdir / f"synthetic_{rows}.csv", tickers, days, SEED)
    runs = [_timed_run(csv_path, workdir) for _ in range(repeats)]
    return Measurement(
        rows=tickers * days,
        tickers=tickers,
        days=days,
        load_s=round(statistics.median(r[0] for r in runs), 3),
        dbt_build_wall_s=round(statistics.median(r[1] for r in runs), 3),
        dbt_build_exec_s=round(statistics.median(r[2] for r in runs), 3),
        dbt_nodes_passed=runs[0][3],
    )


def _hardware() -> str:
    chip = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        brand = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        chip = brand or chip
    return f"{chip}, {platform.system()} {platform.release()}"


def environment() -> dict[str, str]:
    return {
        "hardware": _hardware(),
        "python": platform.python_version(),
        "duckdb": version("duckdb"),
        "dbt-core": version("dbt-core"),
        "dbt-duckdb": version("dbt-duckdb"),
    }


def to_markdown(results: Sequence[Measurement], env: dict[str, str], repeats: int) -> str:
    lines = [
        "| Rows (synthetic) | Tickers x days | Load (s) | dbt build wall (s) "
        "| dbt build exec (s) | Nodes passed |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for m in results:
        lines.append(
            f"| {m.rows:,} | {m.tickers} x {m.days} | {m.load_s:.3f} | {m.dbt_build_wall_s:.3f} "
            f"| {m.dbt_build_exec_s:.3f} | {m.dbt_nodes_passed} |"
        )
    setup = ", ".join(f"{key} {value}" for key, value in env.items() if key != "hardware")
    lines += [
        "",
        f"Median of {repeats} runs on {env['hardware']}; {setup}. Seed {SEED}.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        results = [measure(size, args.repeats, Path(tmp)) for size in args.sizes]
    env = environment()
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*asdict(results[0]), *env])
        writer.writeheader()
        writer.writerows({**asdict(m), **env} for m in results)
    markdown = to_markdown(results, env, args.repeats)
    (args.out / "results.md").write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
