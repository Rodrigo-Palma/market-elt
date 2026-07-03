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

## Results

Measured locally on an Apple M3 Max (macOS, Python 3.12), single run of the
full pipeline against the bundled sample data:

| Step | What runs | Outcome | Wall time |
|---|---|---|---|
| Extract-Load | `python -m market_elt.ingest` | 15 rows → `raw.prices` | ~0.6 s |
| Transform + test | `dbt build` (1 view, 1 table, 8 data tests) | 10/10 PASS | ~2.7 s (0.19 s execution) |
| Marts | `daily_metrics` | 3 tickers × 5 observations, close + annualized volatility | — |

The dataset is intentionally tiny: the point of this repo is the **shape** of
the pipeline (EL → dbt staging → marts → data-quality gates, all reproducible
offline), not data volume. Swap `data/sample/prices.csv` for a real feed and
the same contract holds.

## Development

```bash
make install   # uv sync --extra dev
make lint      # ruff
make type      # mypy
make test      # pytest (load + transform)
make build     # ingest + dbt build (run + data-quality tests)
```

## Layout

```
src/market_elt/      extract-load step (Python + DuckDB)
transform/           dbt project (models + tests + profile)
data/sample/         bundled sample prices
tests/               pytest for the load and transform steps
```

## License

MIT — see [LICENSE](LICENSE).

## Author

**Rodrigo Stachlewski Palma** — Senior Data & AI Engineer.
[LinkedIn](https://linkedin.com/in/rodrigospalma/) · [GitHub](https://github.com/Rodrigo-Palma)
