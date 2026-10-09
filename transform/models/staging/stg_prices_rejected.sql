-- Raw rows that break a row-level rule, with the reason.
-- The complement of stg_prices: count(raw) = count(stg_prices) + count(this).
select
    cast(date as date)                   as price_date,
    cast(upper(trim(ticker)) as varchar) as ticker,
    cast(close as double)                as close,
    cast({{ price_reject_reason('ticker', 'close') }} as varchar) as reject_reason
from {{ source('raw', 'prices') }}
where {{ price_reject_reason('ticker', 'close') }} is not null
