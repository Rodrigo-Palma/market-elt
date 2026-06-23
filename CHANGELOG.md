# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-23

### Added
- Extract-Load step (Python + DuckDB) loading prices into `raw.prices`.
- dbt project: `stg_prices` (staging view) and `daily_metrics` (mart table).
- Data-quality tests: not_null, unique, and a singular positive-close test.
- Bundled sample data so `dbt build` runs offline.
- Tooling: ruff, mypy, pytest, GitHub Actions CI running the full ELT.
