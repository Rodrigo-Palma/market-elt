with source as (
    select * from {{ source('raw', 'prices') }}
)

select
    cast(date as date)   as price_date,
    upper(trim(ticker))  as ticker,
    cast(close as double) as close
from source
where close is not null
