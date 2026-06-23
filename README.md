# market-elt — Reproducible DuckDB + dbt ELT Pipeline

[![CI](https://github.com/Rodrigo-Palma/market-elt/actions/workflows/ci.yml/badge.svg)](https://github.com/Rodrigo-Palma/market-elt/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![dbt](https://img.shields.io/badge/dbt-duckdb-FF694B.svg)](https://github.com/duckdb/dbt-duckdb)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A small, fully reproducible **analytics-engineering** pipeline: load market
> prices into **DuckDB**, transform them with **dbt** (staging → marts), and
> enforce **data-quality tests** — all locally, no warehouse, no paid services.

## Why

A compact end-to-end Data Engineering showcase: `extract-load (Python + DuckDB)
→ transform (dbt) → test (dbt)`. It runs offline against bundled sample data, so
`dbt build` is green in CI with zero infrastructure.

## Pipeline

```
data/sample/prices.csv
        │  load (Python + DuckDB)
        ▼
   raw.prices            (DuckDB)
        │  dbt
        ▼
   stg_prices            (view: typed, cleaned)   ── tests: not_null
        │
        ▼
   daily_metrics         (table: per-ticker observations, last close,
        │                 annualized volatility)  ── tests: not_null, unique
        ▼
   + singular test: close prices must be strictly positive
```

## Quickstart

```bash
git clone https://github.com/Rodrigo-Palma/market-elt.git
cd market-elt
uv sync --extra dev

# Extract-Load: sample CSV → DuckDB (raw.prices)
uv run python -m market_elt.ingest

# Transform + test (dbt)
uv run dbt build --project-dir transform --profiles-dir transform

# Inspect the result
uv run python -c "import duckdb; print(duckdb.connect('market_elt.duckdb').sql('select * from daily_metrics'))"
```

## Development

```bash
make install   # uv sync --extra dev
make lint      # ruff
make type      # mypy
make test      # pytest (load step)
make build     # ingest + dbt build (run + data-quality tests)
```

## Layout

```
src/market_elt/      extract-load step (Python + DuckDB)
transform/           dbt project (models + tests + profile)
data/sample/         bundled sample prices
tests/               pytest for the load step
```

## License

MIT — see [LICENSE](LICENSE).

## Author

**Rodrigo Stachlewski Palma** — Data & AI Engineer.
[LinkedIn](https://linkedin.com/in/rodrigospalma/) · [GitHub](https://github.com/Rodrigo-Palma)
