"""What the point-in-time design is worth: a baseline on features_daily vs a leak.

On SYNTHETIC random walks (market_elt.synthetic) the next day's return is
independent of the past by construction, so no honest feature can predict its
sign: the expected out-of-sample accuracy is 50%. The script builds the
pipeline, then fits the same one-parameter rule twice:

- point-in-time: ``rolling_mean_return_20d`` from ``features_daily``
  (trailing 20 rows, ending at D);
- leaky: the same mean over a centered window (10 preceding, 9 following),
  the kind of window the causal invariance test rejects.

The rule predicts "next return > 0" from the sign of the feature, with the
direction (momentum or reversal) chosen on the train dates. Train and test
are split by date, with the test block strictly after the train block. The
label is the next row's ``return_1d``, which is exactly what the leaky window
reads. Accuracy is reported with a 95% Wilson interval.

Run: uv run python benchmarks/leakage.py
"""

from __future__ import annotations

import argparse
import math
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import duckdb

from market_elt.dbt_runner import run_dbt
from market_elt.ingest import load_prices
from market_elt.synthetic import write_synthetic_prices

SEED: Final = 20260102
TICKERS: Final = 200
DAYS: Final = 1000
TRAIN_FRACTION: Final = 0.7
Z_95: Final = 1.959963984540054
OUT_FILE: Final = Path(__file__).parent / "leakage.md"

# One row per (ticker, date) with a full trailing window and a known label.
DATASET_SQL: Final = """
with leaky as (
    select
        ticker,
        price_date,
        avg(return_1d) over (
            partition by ticker order by price_date
            rows between 10 preceding and 9 following
        ) as centered_mean
    from features_daily
),
labeled as (
    select
        f.ticker,
        f.price_date,
        f.rolling_mean_return_20d as point_in_time,
        l.centered_mean as leaky,
        lead(f.return_1d) over (partition by f.ticker order by f.price_date) as next_return
    from features_daily as f
    join leaky as l using (ticker, price_date)
    where f.n_obs_window = 20
)
select *
from labeled
where next_return is not null and next_return != 0
"""


@dataclass(frozen=True)
class Score:
    feature: str
    direction: str
    train_accuracy: float
    test_accuracy: float
    test_low: float
    test_high: float
    n_test: int


def wilson(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    if n == 0:
        raise ValueError("Wilson interval needs at least one trial")
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return center - half, center + half


def _hits(con: duckdb.DuckDBPyConnection, feature: str, sign: int, split: str) -> tuple[int, int]:
    row = con.execute(
        f"""
        select
            count_if(({sign} * {feature} > 0) = (next_return > 0)),
            count(*)
        from dataset
        where {feature} is not null and {feature} != 0
          and price_date {split} (select cutoff from split)
        """
    ).fetchone()
    if row is None:
        raise RuntimeError(f"no rows for {feature}")
    return int(row[0]), int(row[1])


def score(con: duckdb.DuckDBPyConnection, feature: str) -> Score:
    """Choose the rule's direction on train, then score it once on test."""
    train = {sign: _hits(con, feature, sign, "<") for sign in (1, -1)}
    sign = max(train, key=lambda s: train[s][0] / train[s][1])
    hits, n = _hits(con, feature, sign, ">=")
    low, high = wilson(hits, n)
    return Score(
        feature=feature,
        direction="momentum" if sign == 1 else "reversal",
        train_accuracy=train[sign][0] / train[sign][1],
        test_accuracy=hits / n,
        test_low=low,
        test_high=high,
        n_test=n,
    )


def evaluate(db: Path, train_fraction: float) -> list[Score]:
    con = duckdb.connect(str(db))
    try:
        con.execute(f"create temp table dataset as {DATASET_SQL}")
        con.execute(
            "create temp table split as select quantile_disc(price_date, ?) as cutoff"
            " from (select distinct price_date from dataset)",
            [train_fraction],
        )
        return [score(con, feature) for feature in ("point_in_time", "leaky")]
    finally:
        con.close()


def build(workdir: Path, tickers: int, days: int, seed: int) -> Path:
    csv_path = write_synthetic_prices(workdir / "synthetic.csv", tickers, days, seed)
    db = workdir / "leakage.duckdb"
    load_prices(csv_path, db)
    run = run_dbt("build", db, workdir / "target")
    if run.returncode != 0 or run.summary.status != "success":
        raise RuntimeError(f"dbt build failed:\n{run.stdout}")
    return db


def to_markdown(scores: Sequence[Score], tickers: int, days: int, seed: int) -> str:
    lines = [
        "| Feature | Rule (fit on train) | Train accuracy | Test accuracy | 95% Wilson | n test |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for s in scores:
        lines.append(
            f"| {s.feature} | {s.direction} | {s.train_accuracy:.2%} | {s.test_accuracy:.2%} "
            f"| {s.test_low:.2%} to {s.test_high:.2%} | {s.n_test:,} |"
        )
    lines += [
        "",
        f"Synthetic random walks: {tickers} tickers x {days} weekdays, seed {seed}; "
        f"train on the first {TRAIN_FRACTION:.0%} of dates, test on the rest.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> list[Score]:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--tickers", type=int, default=TICKERS)
    parser.add_argument("--days", type=int, default=DAYS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=OUT_FILE)
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        db = build(Path(tmp), args.tickers, args.days, args.seed)
        scores = evaluate(db, TRAIN_FRACTION)
    markdown = to_markdown(scores, args.tickers, args.days, args.seed)
    args.out.write_text(markdown)
    print(markdown)
    return scores


if __name__ == "__main__":
    main()
