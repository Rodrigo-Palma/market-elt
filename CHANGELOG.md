# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-10-09

### Added
- Typed CSV contract in the loader (header, column order, types, date
  format). A violation raises `ContractViolationError` and keeps the previous
  `raw.prices`.
- Enforced dbt contracts on `stg_prices`, `stg_prices_rejected`,
  `daily_metrics` and `features_daily`.
- `stg_prices_rejected` with `reject_reason`, gated by `row_count_at_most`
  and the `max_rejected_rows` var (default 0).
- Uniqueness test on `(ticker, price_date)`, source column tests, and
  `dbt source freshness` on `loaded_at` (warn 24h, error 72h).
- Negative tests: one broken fixture per gate, each asserting the failing
  node from `run_results.json`.
- dbt unit test for `daily_metrics` against an independent stdlib reference.
- `features_daily`: point-in-time features with a causal invariance test.
- `market-elt run`: load, `dbt build` and a row in `meta.pipeline_runs`, with
  JSON logs. `make pipeline` runs it.
- Multi-stage Dockerfile, CI job that runs the image, dbt docs on GitHub Pages.
- Synthetic scale benchmark (1e4, 1e5, 1e6 rows) with recorded results.
- ADRs 0001 to 0003.

### Changed
- `stg_prices` no longer drops null closes silently; rejected rows are
  counted and fail the build by default.
- `annualized_volatility` is rounded to 10 decimals.
- `__version__` comes from package metadata; installs use `uv sync --locked`.
- The `market-elt` entry point is now the CLI (`run`, `load`).

### Removed
- The singular `assert_positive_close` test, replaced by the rejection gate.

## [0.1.0] - 2026-06-23

### Added
- Extract-Load step (Python + DuckDB) loading prices into `raw.prices`.
- dbt project: `stg_prices` (staging view) and `daily_metrics` (mart table).
- Data-quality tests: not_null, unique, and a singular positive-close test.
- Bundled sample data so `dbt build` runs offline.
- Tooling: ruff, mypy, pytest, GitHub Actions CI running the full ELT.

[0.2.0]: https://github.com/Rodrigo-Palma/market-elt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Rodrigo-Palma/market-elt/releases/tag/v0.1.0
