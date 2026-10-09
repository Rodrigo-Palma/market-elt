{#
    Fails for every combination of `combination_of_columns` that appears more
    than once. Same contract as dbt_utils.unique_combination_of_columns, kept
    local so the project has no package dependency.
#}
{% test unique_combination_of_columns(model, combination_of_columns) %}
    {%- set columns = combination_of_columns | join(', ') %}
    select {{ columns }}, count(*) as n_rows
    from {{ model }}
    group by {{ columns }}
    having count(*) > 1
{% endtest %}
