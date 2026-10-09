# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-10-09

### Fixed
- `nan` and `inf` closes and tickers made only of spaces passed every gate
  and reached `daily_metrics` (a run exited 0 with `last_close = nan` and a
  ticker `''`). `price_reject_reason` now quarantines them as `nan_close`,
  `infinite_close` and `blank_ticker`.
- A missing CSV or a dbt crash that leaves no `run_results.json` (bad
  `--vars`, parse error) left no row in `meta.pipeline_runs`. Both are now
  recorded (`load_failed`, `crashed`) and re-raised; the CLI exits 1.
- A non-zero dbt exit with a successful artifact counted as success; it is
  now recorded as `nonzero_exit`.

### Added
- Singular test `assert_staging_reconciles_with_raw`:
  `count(raw) = count(stg_prices) + count(stg_prices_rejected)`.
- Recency gate on the data, `max_date_at_most_days_old` on
  `stg_prices.price_date`, off by default; `market-elt run
  --max-price-age-days N [--as-of YYYY-MM-DD]` turns it on.
- `scripts/mutations.py` (`make mutate`, manual `Mutations` workflow): 9
  mutations applied to a temp copy, each required to turn its test red.
- `benchmarks/leakage.py` (`make leakage`): the point-in-time feature vs a
  centered window on synthetic random walks, with Wilson intervals.
- 1e7 rows in the scale benchmark.

### Changed
- CI no longer runs `dbt source freshness` right after the pipeline, where
  it could not fail; `make all` drops it too.
- dbt anonymous usage tracking is off; `transform/.user.yml` is untracked.
- CI declares `permissions: contents: read`; actions are pinned by commit
  SHA and the Docker base images by digest, with Dependabot for both.

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

[0.3.0]: https://github.com/Rodrigo-Palma/market-elt/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Rodrigo-Palma/market-elt/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Rodrigo-Palma/market-elt/releases/tag/v0.1.0
