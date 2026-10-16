-- Point-in-time features, one row per (ticker, price_date).
-- Every value on date D reads only prices dated <= D: lag() looks one row
-- back and every window ends at the current row. Nothing here may use
-- lead(), "following" or a whole-partition aggregate.
-- Values are rounded to 10 decimals so they do not depend on float
-- accumulation order inside the window operator.
--
-- Incremental (ADR 0004): raw.prices is replaced on every load, so an
-- incremental run reads it whole and keeps, per ticker, the dates after the
-- last one already in this table plus `features_lookback_rows` earlier rows
-- as window context. Only the new dates are written. Rows at or before a
-- ticker's last loaded date are never revised; a revised history needs
-- `dbt build --full-refresh`.
{{
    config(
        materialized='incremental',
        unique_key=['ticker', 'price_date'],
        incremental_strategy='delete+insert',
        on_schema_change='fail',
    )
}}

with prices as (
{% if is_incremental() %}
    select
        s.ticker,
        s.price_date,
        s.close,
        l.loaded_until
    from {{ ref('stg_prices') }} as s
    left join (
        select ticker, max(price_date) as loaded_until
        from {{ this }}
        group by ticker
    ) as l using (ticker)
    qualify l.loaded_until is null
        or s.price_date > l.loaded_until
        or row_number() over (
            partition by s.ticker, s.price_date <= l.loaded_until
            order by s.price_date desc
        ) <= {{ var('features_lookback_rows') }}
{% else %}
    select ticker, price_date, close, cast(null as date) as loaded_until
    from {{ ref('stg_prices') }}
{% endif %}
),

returns as (
    select
        ticker,
        price_date,
        close,
        loaded_until,
        close / lag(close) over (partition by ticker order by price_date) - 1
            as return_1d
    from prices
),

features as (
    select
        ticker,
        price_date,
        close,
        loaded_until,
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
)

select
    ticker,
    price_date,
    close,
    return_1d,
    rolling_vol_20d,
    rolling_mean_return_20d,
    n_obs_window
from features
-- context rows feed the windows of the new dates and are not written again
where loaded_until is null or price_date > loaded_until
