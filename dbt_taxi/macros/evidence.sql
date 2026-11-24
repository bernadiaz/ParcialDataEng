{#- Helpers of the evidence models (models/evidence): what the Spanish reports and Superset both read. -#}

{#- 'YYYY-MM' from integer year/month columns. -#}
{% macro mes_label(year_column, month_column) -%}
    concat(cast({{ year_column }} as varchar), '-', lpad(cast({{ month_column }} as varchar), 2, '0'))
{%- endmacro %}

{#- Share in %, in double precision on both engines (same operations as share() in src/interpretacion.py). -#}
{% macro pct_of(part, total) -%}
    100.0 * cast({{ part }} as double) / nullif(cast({{ total }} as double), 0)
{%- endmacro %}

{#- Change in %, in double precision on both engines (same operations as variacion() in src/interpretacion.py). -#}
{% macro var_pct(new, old) -%}
    100.0 * (cast({{ new }} as double) - cast({{ old }} as double)) / nullif(cast({{ old }} as double), 0)
{%- endmacro %}

{#- Zone name of the lookup. 264 and a few legacy ids have none ("N/A"): they are named by their id, exactly
    like zone_name() in src/interpretacion.py. -#}
{% macro zone_label(location_column, zone_column) -%}
    case
        when {{ zone_column }} is not null and trim({{ zone_column }}) <> '' and upper(trim({{ zone_column }})) <> 'N/A'
            then trim({{ zone_column }})
        when {{ location_column }} = 264 then 'zona desconocida (264)'
        when {{ location_column }} = 265 then 'fuera de NYC (265)'
        else concat('zona ', cast({{ location_column }} as varchar))
    end
{%- endmacro %}

{#- Payment type names of the TLC data dictionary (the same ones as sql/q4_tip_pct_by_payment.sql). -#}
{% macro payment_label(payment_column) -%}
    case {{ payment_column }}
        when 0 then 'Flex Fare' when 1 then 'Credit card' when 2 then 'Cash' when 3 then 'No charge'
        when 4 then 'Dispute' when 5 then 'Unknown' when 6 then 'Voided trip' else 'Sin dato'
    end
{%- endmacro %}

{#- Day names in Spanish (ISO: 1 = Monday ... 7 = Sunday). -#}
{% macro dia_semana(dow_column) -%}
    case {{ dow_column }}
        when 1 then 'lunes' when 2 then 'martes' when 3 then 'miércoles' when 4 then 'jueves'
        when 5 then 'viernes' when 6 then 'sábado' when 7 then 'domingo'
    end
{%- endmacro %}
