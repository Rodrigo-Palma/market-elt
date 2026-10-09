"""Extract-Load step: load a prices CSV into DuckDB as ``raw.prices``.

This is the only place that touches source data; transformations live in dbt.
The CSV is read against an explicit contract (column names, order and types),
so a renamed column or an unparseable value fails the load instead of being
inferred into a different schema.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Final

import duckdb

from market_elt import config

RAW_COLUMNS: Final[dict[str, str]] = {"date": "DATE", "ticker": "VARCHAR", "close": "DOUBLE"}
DATE_FORMAT: Final = "%Y-%m-%d"


class ContractViolationError(ValueError):
    """The source file does not match the declared raw contract."""


def _check_header(csv_path: Path) -> None:
    with csv_path.open(newline="") as handle:
        header = next(csv.reader(handle), [])
    expected = list(RAW_COLUMNS)
    if [name.strip() for name in header] != expected:
        raise ContractViolationError(
            f"{csv_path.name}: header {header} does not match the contract {expected}"
        )


def _read_csv_sql() -> str:
    columns = ", ".join(f"'{name}': '{dtype}'" for name, dtype in RAW_COLUMNS.items())
    return (
        "SELECT *, now() AS loaded_at FROM read_csv($path, header = true, auto_detect = false,"
        f" columns = {{{columns}}}, dateformat = '{DATE_FORMAT}')"
    )


def load_prices(csv_path: str | Path, db_path: str | Path) -> int:
    """Replace ``raw.prices`` in the DuckDB at ``db_path`` with ``csv_path``.

    The replace is a single statement: if the file breaks the contract, the
    previous table is left untouched and :class:`ContractViolationError` is
    raised. Every row gets the same ``loaded_at`` (the load transaction's
    timestamp), which ``dbt source freshness`` reads. Returns the number of
    rows loaded.
    """
    path = Path(csv_path)
    _check_header(path)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        try:
            con.execute(
                f"CREATE OR REPLACE TABLE raw.prices AS {_read_csv_sql()}",
                {"path": str(path)},
            )
        except (duckdb.ConversionException, duckdb.InvalidInputException) as exc:
            raise ContractViolationError(f"{path.name}: {exc}") from exc
        result = con.execute("SELECT count(*) FROM raw.prices").fetchone()
        return int(result[0]) if result else 0
    finally:
        con.close()


def main() -> None:
    rows = load_prices(config.SAMPLE_CSV, config.DB_PATH)
    print(f"Loaded {rows} rows into raw.prices at {config.DB_PATH}")


if __name__ == "__main__":
    main()
