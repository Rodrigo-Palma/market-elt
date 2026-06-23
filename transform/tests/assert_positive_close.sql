-- Data quality: close prices must be strictly positive.
-- The test fails if this query returns any rows.
select price_date, ticker, close
from {{ ref('stg_prices') }}
where close <= 0
