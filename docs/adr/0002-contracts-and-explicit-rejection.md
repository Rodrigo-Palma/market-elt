# ADR 0002: Typed contracts at every boundary, and explicit rejection instead of silent filters

- Status: accepted
- Date: 2026-10-09

## Context

Version 0.1.0 read the CSV with inferred types, and `stg_prices` filtered
`where close is not null` and then tested `not_null` on `close`. That test
could never fail: null rows disappeared without a count. Nothing checked that
`(ticker, price_date)` was unique, so a duplicated day passed every test and
skewed `lag()` and the volatility.

## Decision

1. **Load contract.** `market_elt.ingest` reads the CSV with declared column
   names, order, types and date format (`auto_detect = false`). A different
   header or an unparseable value raises `ContractViolationError`, and the
   previous `raw.prices` stays in place because the replace is one statement.
2. **Model contracts.** `stg_prices`, `stg_prices_rejected`, `daily_metrics`
   and `features_daily` have `contract: {enforced: true}` with a `data_type`
   per column. A type change in SQL without a matching change in the contract
   fails the build.
3. **Explicit rejection.** Row-level rules live in one macro
   (`price_reject_reason`). A raw row lands in exactly one of `stg_prices`
   or `stg_prices_rejected`, the latter with its reason. The test
   `row_count_at_most` on `stg_prices_rejected` fails the build when it holds
   more than `max_rejected_rows` rows (default 0). An operator can accept a
   known number of bad rows with `--max-rejected-rows N`, and they are still
   counted in `meta.pipeline_runs.rows_rejected`.
4. **Natural key.** A local `unique_combination_of_columns` test on
   `(ticker, price_date)`, with no package dependency.
5. **Every gate is shown failing.** `tests/test_quality_gates.py` feeds one
   broken file per gate and asserts the build fails on that node, read from
   `run_results.json`.

## Consequences

- A bad file fails loudly by default. Quarantine is opt-in and bounded.
- The rejection rules have one definition, so the two staging models cannot
  drift apart.
- Rows without a ticker or a date fail the source `not_null` tests instead of
  going to quarantine: a row that cannot be identified cannot be reviewed.

## Alternatives considered

- **Fail on the first bad row in the loader**: simpler, but no way to accept
  a known, counted number of bad rows.
- **dbt_utils**: one test needed, not worth a package dependency and a
  `dbt deps` step.
