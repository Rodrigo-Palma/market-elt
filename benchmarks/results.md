| Rows (synthetic) | Tickers x days | Load (s) | dbt build wall (s) | dbt build exec (s) | Nodes passed |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 10 x 1000 | 0.012 | 1.516 | 0.365 | 25 |
| 100,000 | 100 x 1000 | 0.042 | 1.609 | 0.414 | 25 |
| 1,000,000 | 1000 x 1000 | 0.136 | 1.855 | 0.695 | 25 |
| 10,000,000 | 10000 x 1000 | 0.410 | 3.196 | 1.955 | 25 |

Median of 3 runs on Apple M3 Max, Darwin 27.0.0; python 3.12.13, duckdb 1.5.6, dbt-core 1.12.6, dbt-duckdb 1.11.0. Seed 20260101.
