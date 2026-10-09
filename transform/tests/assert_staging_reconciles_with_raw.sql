-- Every raw row lands in exactly one of stg_prices and stg_prices_rejected.
-- Returns one row (and fails) when count(raw) differs from the sum, which
-- would mean a rule dropped rows silently or sent one row to both models.
with counts as (
    select
        (select count(*) from {{ source('raw', 'prices') }})   as n_raw,
        (select count(*) from {{ ref('stg_prices') }})          as n_valid,
        (select count(*) from {{ ref('stg_prices_rejected') }}) as n_rejected
)

select n_raw, n_valid, n_rejected
from counts
where n_raw != n_valid + n_rejected
