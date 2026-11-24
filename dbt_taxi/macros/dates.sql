{#- ISO day of week (1 = Monday ... 7 = Sunday), portable between Snowflake and DuckDB. -#}
{% macro dow_iso(column) -%}
    {{ return(adapter.dispatch('dow_iso')(column)) }}
{%- endmacro %}

{% macro snowflake__dow_iso(column) -%}
    dayofweekiso({{ column }})
{%- endmacro %}

{% macro default__dow_iso(column) -%}
    isodow({{ column }})
{%- endmacro %}

{% macro day_name(dow_column) -%}
    case {{ dow_column }}
        when 1 then 'Monday' when 2 then 'Tuesday' when 3 then 'Wednesday' when 4 then 'Thursday'
        when 5 then 'Friday' when 6 then 'Saturday' when 7 then 'Sunday'
    end
{%- endmacro %}

{#- First day of a month from integer year/month columns. -#}
{% macro month_start(year_column, month_column) -%}
    cast(concat(cast({{ year_column }} as varchar), '-', lpad(cast({{ month_column }} as varchar), 2, '0'), '-01') as date)
{%- endmacro %}
