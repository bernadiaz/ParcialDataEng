-- Grain: one row per comparison and day of the week (calendar effect of question 6): how many times the day appears
-- in each month, its trips and its trips per day. viajes_con_calendario_anterior = trips per day of the month x
-- times that day appears in the same month of the previous year.
with calendario as (

    select year, month, day_of_week_iso, count(*) as dias
    from {{ ref('dim_date') }}
    group by year, month, day_of_week_iso

),

viajes as (

    select d.year, d.month, d.day_of_week_iso, sum(a.trips) as viajes
    from {{ ref('agg_day') }} as a
    inner join {{ ref('dim_date') }} as d on d.date_key = a.pickup_date
    group by d.year, d.month, d.day_of_week_iso

),

por_dia as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        cast(k.day_of_week_iso as integer) as dia_iso,
        max(case when k.year = c.anio then k.dias end) as dias_mes,
        max(case when k.year = c.anio_anterior then k.dias end) as dias_anterior,
        cast(max(case when k.year = c.anio then coalesce(v.viajes, 0) end) as bigint) as viajes_mes,
        cast(max(case when k.year = c.anio_anterior then coalesce(v.viajes, 0) end) as bigint) as viajes_anterior
    from {{ ref('ev_comparaciones') }} as c
    inner join calendario as k on k.month = c.mes_num and k.year in (c.anio, c.anio_anterior)
    left join viajes as v on v.year = k.year and v.month = k.month and v.day_of_week_iso = k.day_of_week_iso
    group by c.mes, c.anio, c.mes_num, k.day_of_week_iso

),

promedios as (

    select
        por_dia.*,
        cast(viajes_mes as double) / nullif(dias_mes, 0) as viajes_por_dia_mes,
        cast(viajes_anterior as double) / nullif(dias_anterior, 0) as viajes_por_dia_anterior
    from por_dia

)

select
    promedios.*,
    {{ dia_semana('dia_iso') }} as dia_semana,
    concat(cast(dia_iso as varchar), ' ', {{ dia_semana('dia_iso') }}) as dia_etiqueta,
    {{ var_pct('viajes_por_dia_mes', 'viajes_por_dia_anterior') }} as variacion_por_dia_pct,
    viajes_por_dia_mes * dias_anterior as viajes_con_calendario_anterior
from promedios
