"""Command line: ``market-elt run`` (load + dbt build + run log) and ``market-elt load``."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from market_elt import config
from market_elt.ingest import ContractViolationError, load_prices
from market_elt.logs import get_logger
from market_elt.pipeline import run_pipeline

DEFAULT_TARGET = config.ROOT / "transform" / "target"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market-elt")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("run", "load the CSV, run dbt build and record the run"),
        ("load", "only load the CSV into raw.prices"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--csv", type=Path, default=config.SAMPLE_CSV)
        command.add_argument("--db", type=Path, default=config.DB_PATH)
    run = commands.choices["run"]
    run.add_argument("--target-path", type=Path, default=DEFAULT_TARGET)
    run.add_argument(
        "--max-rejected-rows",
        type=int,
        default=None,
        help="rows allowed in stg_prices_rejected before the build fails (default 0)",
    )
    run.add_argument(
        "--max-price-age-days",
        type=int,
        default=None,
        help="fail when the latest price_date is older than this many days (default: off)",
    )
    run.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="reference date for --max-price-age-days, YYYY-MM-DD (default: today)",
    )
    return parser


def dbt_vars(args: argparse.Namespace) -> tuple[str, ...]:
    """The ``--vars`` argument for dbt, holding only the options that were set."""
    values: dict[str, object] = {}
    if args.max_rejected_rows is not None:
        values["max_rejected_rows"] = args.max_rejected_rows
    if args.max_price_age_days is not None:
        values["max_price_age_days"] = args.max_price_age_days
    if args.as_of is not None:
        values["as_of_date"] = args.as_of.isoformat()
    return ("--vars", json.dumps(values)) if values else ()


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = _parser().parse_args(argv)
    if args.command == "load":
        try:
            rows = load_prices(args.csv, args.db)
        except (ContractViolationError, OSError) as exc:
            get_logger().error("load.failed", extra={"fields": {"error": str(exc)}})
            return 1
        get_logger().info("load.done", extra={"fields": {"rows": rows, "db": str(args.db)}})
        return 0
    try:
        run = run_pipeline(args.csv, args.db, args.target_path, dbt_vars(args))
    except (ContractViolationError, OSError, RuntimeError):
        # Already recorded in meta.pipeline_runs and logged by run_pipeline.
        return 1
    return 0 if run.succeeded else 1


def entrypoint() -> None:
    raise SystemExit(main())
