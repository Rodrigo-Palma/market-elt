| Feature | Rule (fit on train) | Train accuracy | Test accuracy | 95% Wilson | n test |
|---|---|---:|---:|---:|---:|
| point_in_time | reversal | 50.29% | 50.18% | 49.77% to 50.58% | 58,798 |
| leaky | momentum | 56.81% | 57.10% | 56.70% to 57.50% | 58,798 |

Synthetic random walks: 200 tickers x 1000 weekdays, seed 20260102; train on the first 70% of dates, test on the rest.
