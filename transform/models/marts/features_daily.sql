-- Point-in-time features, one row per (ticker, price_date).
-- Every value on date D reads only prices dated <= D: lag() looks one row
-- back and every window ends at the current row. Nothing here may use
-- lead(), "following" or a whole-partition aggregate.
-- Values are rounded to 10 decimals so they do not depend on float
-- accumulation order inside the window operator.
with returns as (
    select
        ticker,
        price_date,
        close,
        close / lag(close) over (partition by ticker order by price_date) - 1
            as return_1d
    from {{ ref('stg_prices') }}
)

select
    ticker,
    price_date,
    close,
    round(return_1d, 10)                                    as return_1d,
    round(stddev_samp(return_1d) over trailing_20, 10)      as rolling_vol_20d,
    round(avg(return_1d) over trailing_20, 10)              as rolling_mean_return_20d,
    count(return_1d) over trailing_20                       as n_obs_window
from returns
window trailing_20 as (
    partition by ticker
    order by price_date
    rows between 19 preceding and current row
)
