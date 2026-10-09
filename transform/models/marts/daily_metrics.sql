-- Per-ticker summary of the validated prices.
-- annualized_volatility: sample stddev of daily simple returns times
-- sqrt(252), rounded to 10 decimals so the value does not depend on float
-- accumulation order. Null when a ticker has fewer than 3 prices.
with returns as (
    select
        ticker,
        price_date,
        close,
        close / lag(close) over (partition by ticker order by price_date) - 1
            as daily_return
    from {{ ref('stg_prices') }}
)

select
    ticker,
    count(*)                                            as observations,
    max(price_date)                                     as last_date,
    arg_max(close, price_date)                          as last_close,
    round(stddev_samp(daily_return) * sqrt(252), 10)    as annualized_volatility
from returns
group by ticker
