{#-
  Incremental batch = the months processed by `make all` (DBT_MONTHS="2025-01,2024-01").
  Empty DBT_MONTHS -> every month in RAW (full reprocess of the incremental models).
-#}
{% macro processed_months() -%}
    {%- set raw = env_var('DBT_MONTHS', '') | trim -%}
    {%- set months = [] -%}
    {%- for value in raw.split(',') if value | trim -%}
        {%- set parts = (value | trim).split('-') -%}
        {%- do months.append({'year': parts[0] | int, 'month': parts[1] | int}) -%}
    {%- endfor -%}
    {{ return(months) }}
{%- endmacro %}

{% macro months_filter(year_column='year', month_column='month') -%}
    {%- set months = processed_months() -%}
    {%- if months | length == 0 -%}
        1 = 1
    {%- else -%}
        (
        {%- for m in months %}
            ({{ year_column }} = {{ m.year }} and {{ month_column }} = {{ m.month }}){{ ' or' if not loop.last }}
        {%- endfor %}
        )
    {%- endif -%}
{%- endmacro %}
