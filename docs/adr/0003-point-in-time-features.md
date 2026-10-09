# ADR 0003: Point-in-time features with a causal invariance test

- Status: accepted
- Date: 2026-10-09

## Context

A model trained on market features is only as honest as its features. If the
value for date D reads any price after D (a centered window, `lead()`, a
whole-partition aggregate), backtests look better than live scoring can ever
be. That leak is easy to write and invisible in a schema test.

## Decision

`features_daily` has one row per `(ticker, price_date)` with `return_1d`,
`rolling_vol_20d`, `rolling_mean_return_20d` and `n_obs_window`. It uses only
`lag()` and windows declared as `rows between 19 preceding and current row`.
The window counts rows present in the data (trading days), not calendar days.
Values appear as soon as they are defined; `n_obs_window` says how many returns
the window holds, so a consumer that wants a full window filters on 20.

The guarantee is tested, not just documented. `tests/test_features_causal.py`
builds the features on 60 days of synthetic history and again on the same
history truncated at a cut date T, for two cuts, and requires identical rows
for every date up to T.

Values are rounded to 10 decimals so the comparison is exact and does not
depend on float summation order inside the window operator.

## Consequences

- The test failed when the window was mutated to
  `10 preceding and 9 following` (both cuts), so it has the power to catch
  the leak it exists for.
- The test proves causality with respect to the rows in the table. It cannot
  catch a leak that arrives in the source itself, such as a price revised
  after the fact.

## Alternatives considered

- **Only document the as-of semantics**: the exact failure mode that the test
  exists to prevent.
- **Compute features in Python**: a second implementation of the same window
  logic to keep in sync with SQL.
