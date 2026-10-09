| Rows (synthetic) | Tickers x days | Load (s) | dbt build wall (s) | dbt build exec (s) | Nodes passed |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 10 x 1000 | 0.011 | 1.472 | 0.382 | 25 |
| 100,000 | 100 x 1000 | 0.039 | 1.503 | 0.411 | 25 |
| 1,000,000 | 1000 x 1000 | 0.123 | 1.814 | 0.708 | 25 |
| 10,000,000 | 10000 x 1000 | 0.364 | 3.290 | 2.152 | 25 |

Median of 3 runs on Apple M3 Max, Darwin 27.0.0; python 3.12.13, duckdb 1.5.4, dbt-core 1.11.11, dbt-duckdb 1.10.1. Seed 20260101.
