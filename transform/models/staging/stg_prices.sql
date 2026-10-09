-- Typed daily close prices that pass every row-level rule.
-- Rows that break a rule are not dropped here: they go to stg_prices_rejected,
-- which is gated by a test, so a rejection is always counted and visible.
select
    cast(date as date)                   as price_date,
    cast(upper(trim(ticker)) as varchar) as ticker,
    cast(close as double)                as close
from {{ source('raw', 'prices') }}
where {{ price_reject_reason('close') }} is null
