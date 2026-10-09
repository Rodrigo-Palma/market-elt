{#
    Row-level rules a price must pass to enter stg_prices.
    Returns NULL for a valid row, otherwise the first rule it breaks.
    stg_prices keeps the NULLs, stg_prices_rejected keeps the rest, so every
    raw row lands in exactly one of the two (checked by the singular test
    assert_staging_reconciles_with_raw).

    The DOUBLE contract of the loader accepts 'nan' and 'inf', and NaN is
    neither NULL nor <= 0, so both need their own rule. A ticker made only of
    spaces is not NULL either: it is trimmed and checked for emptiness.
#}
{% macro price_reject_reason(ticker, close) -%}
    case
        when nullif(trim({{ ticker }}), '') is null then 'blank_ticker'
        when {{ close }} is null then 'null_close'
        when isnan({{ close }}) then 'nan_close'
        when isinf({{ close }}) then 'infinite_close'
        when {{ close }} <= 0 then 'non_positive_close'
    end
{%- endmacro %}
