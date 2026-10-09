| Rows (synthetic) | Tickers x days | Load (s) | dbt build wall (s) | dbt build exec (s) | Nodes passed |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 10 x 1000 | 0.013 | 2.722 | 0.420 | 24 |
| 100,000 | 100 x 1000 | 0.042 | 2.448 | 0.465 | 24 |
| 1,000,000 | 1000 x 1000 | 0.124 | 2.605 | 0.716 | 24 |

Median of 3 runs on Apple M3 Max, Darwin 27.0.0; python 3.12.13, duckdb 1.5.4, dbt-core 1.11.11, dbt-duckdb 1.10.1. Seed 20260101.
