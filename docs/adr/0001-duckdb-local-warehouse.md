# ADR 0001: DuckDB as a local, file-based warehouse

- Status: accepted
- Date: 2026-10-09

## Context

The pipeline has to run the same way on a laptop, in CI and in a container,
with no credentials, no network and no bill. The workload is columnar and
analytical (window functions, group-bys) over a few million rows at most.

## Decision

Use DuckDB, one file per environment, selected by `MARKET_ELT_DB`. dbt talks to
it through `dbt-duckdb`. Every test that builds models gets its own file in a
temporary directory, so tests never share state.

## Consequences

- `market-elt run` and the whole test suite need nothing beyond `uv sync`.
  CI runs the full pipeline, the negative gates and the Docker image on every
  push.
- At the sizes measured in `benchmarks/results.md` (up to 1e6 rows), dbt's own
  execution stays under a second and the wall time is dominated by dbt
  start-up. The numbers say nothing about sizes that do not fit on one machine.
- One writer at a time. That fits a batch pipeline that runs end to end, not
  concurrent loaders. The load and dbt never hold the file at the same time.
- Moving to a server warehouse means a new dbt profile and replacing
  `read_csv` in the loader. The models use standard SQL window functions, with
  two DuckDB-specific functions (`arg_max`, the `read_csv` table function).

## Alternatives considered

- **Postgres in Docker**: a service to start in CI and locally, with no gain
  at this scale.
- **A cloud warehouse**: credentials and cost in CI, and runs that cannot be
  reproduced offline.
