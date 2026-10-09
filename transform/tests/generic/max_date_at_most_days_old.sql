{#
    Fails when the latest `column_name` in `model` is more than
    `max_age_days` calendar days before `as_of` (default: current_date), or
    when the model is empty. Measures how old the data is, not when the file
    was loaded: a fresh load of four-month-old prices fails here and passes
    dbt source freshness.
#}
{% test max_date_at_most_days_old(model, column_name, max_age_days, as_of=none) %}
    {%- set reference = "cast('" ~ as_of ~ "' as date)" if as_of else "current_date" %}
    select
        max({{ column_name }}) as latest,
        {{ reference }} as as_of,
        {{ max_age_days }} as max_age_days
    from {{ model }}
    having max({{ column_name }}) is null
        or max({{ column_name }}) < {{ reference }} - {{ max_age_days }}::integer
{% endtest %}
