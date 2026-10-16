# ADR 0004: Incremental features_daily over a replaced raw table

- Status: accepted
- Date: 2026-10-15

## Context

`features_daily` grows by one row per ticker per trading day, and rebuilding
it on every run recomputes the whole history. An incremental model only
computes the new dates, but its 20-row window and its `lag()` reach back
before them: a run that reads only the new rows cuts the window at the batch
edge and writes wrong values with no error. Trading-day gaps make a calendar
cutoff (`max(price_date) - 20 days`) wrong too, since a ticker that skipped
days needs more calendar days to have 20 rows.

The loader runs `CREATE OR REPLACE raw.prices`, so raw always holds the full
history of the current source file. That had to be settled before the model.

## Decision

Keep the replacing loader. The incremental run reads the replaced raw and,
per ticker, keeps the dates after the last one already in `features_daily`
plus `features_lookback_rows` (a dbt var, 20) rows before it. The 20 rows are
19 for `rows between 19 preceding and current row` and 1 for the `lag()` of
the oldest return in that window. Lookback is counted in rows per ticker, so
gaps and tickers that start or stop trading need no special case. Only the
new dates are written (`delete+insert`, `unique_key [ticker, price_date]`);
the context rows feed the windows and are dropped.

`tests/test_features_incremental.py` loads synthetic history in three stages
with an incremental build after each, builds the same history with
`--full-refresh` in another database, and requires both `EXCEPT ALL`s to be
empty and the row counts to match. Its tickers have gaps at the stage edges,
one starts after the first stage, one stops before it, one has a single row
before it. `scripts/mutations.py` sets the lookback to 19 and writes the
context rows back; the test catches both.

## Consequences

- A ticker's rows at or before its last loaded date are never revised. A
  source that corrects past prices, or a late row older than that date,
  needs `dbt build --full-refresh`. Nothing detects this today.
- Each run still scans all of raw, because raw is replaced. The saving is in
  the window computation and the write, not the read.
- The pipeline stays idempotent: a re-run with the same file finds no new
  dates and writes nothing.

## Alternatives considered

- **Loader appends to raw, filtered by a load watermark**: reads only new
  rows, but the window still needs older context from raw, so raw must keep
  history anyway; it adds dedup of re-sent rows and makes a re-run of the
  same file a source of duplicates. More moving parts to save a read of one
  local table.
- **Stay full refresh**: simplest and always correct, but gives up the
  pattern a daily pipeline is expected to have and leaves the batch-edge
  failure untested for when the volume demands it.
