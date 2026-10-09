{#
    Row-level rules a price must pass to enter stg_prices.
    Returns NULL for a valid row, otherwise the first rule it breaks.
    stg_prices keeps the NULLs, stg_prices_rejected keeps the rest, so every
    raw row lands in exactly one of the two.
#}
{% macro price_reject_reason(close) -%}
    case
        when {{ close }} is null then 'null_close'
        when {{ close }} <= 0 then 'non_positive_close'
    end
{%- endmacro %}
