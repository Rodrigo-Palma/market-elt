"""Command line: ``market-elt run`` (load + dbt build + run log) and ``market-elt load``."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns the process exit code."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "load":
            rows = load_prices(args.csv, args.db)
            get_logger().info("load.done", extra={"fields": {"rows": rows, "db": str(args.db)}})
            return 0
        dbt_args: tuple[str, ...] = ()
        if args.max_rejected_rows is not None:
            dbt_args = ("--vars", f"{{max_rejected_rows: {args.max_rejected_rows}}}")
        run = run_pipeline(args.csv, args.db, args.target_path, dbt_args)
    except ContractViolationError:
        return 1
    return 0 if run.succeeded else 1


def entrypoint() -> None:
    raise SystemExit(main())
