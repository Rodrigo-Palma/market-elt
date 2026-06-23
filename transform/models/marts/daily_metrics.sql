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
    count(*)                                   as observations,
    max(price_date)                            as last_date,
    arg_max(close, price_date)                 as last_close,
    stddev_samp(daily_return) * sqrt(252)      as annualized_volatility
from returns
group by ticker
