"""Extract-Load step: load a prices CSV into DuckDB as ``raw.prices``.

This is the only place that touches source data; transformations live in dbt.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from market_elt import config


def load_prices(csv_path: str | Path, db_path: str | Path) -> int:
    """Load ``csv_path`` into ``raw.prices`` in the DuckDB at ``db_path``.

    Returns the number of rows loaded.
    """
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        relation = con.read_csv(str(csv_path))
        con.register("incoming_prices", relation)
        con.execute("CREATE OR REPLACE TABLE raw.prices AS SELECT * FROM incoming_prices")
        result = con.execute("SELECT count(*) FROM raw.prices").fetchone()
        return int(result[0]) if result else 0
    finally:
        con.close()


def main() -> None:
    rows = load_prices(config.SAMPLE_CSV, config.DB_PATH)
    print(f"Loaded {rows} rows into raw.prices at {config.DB_PATH}")


if __name__ == "__main__":
    main()
