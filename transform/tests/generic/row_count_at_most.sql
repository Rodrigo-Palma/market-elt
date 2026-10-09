{#
    Fails when `model` holds more than `max_rows` rows. Used on
    stg_prices_rejected: the tolerance is the `max_rejected_rows` var
    (default 0), so any rejected row fails the build unless the operator
    raises the tolerance explicitly.
#}
{% test row_count_at_most(model, max_rows) %}
    select count(*) as n_rows
    from {{ model }}
    having count(*) > {{ max_rows }}
{% endtest %}
