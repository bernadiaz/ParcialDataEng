-- Grain: one row per calendar month of every year with data: the 12 months of the year, loaded or not.
-- estado says whether the year-over-year comparison of that month is possible with what is loaded.
with anios as (

    select distinct year as anio from {{ ref('agg_month_profile') }}

),

meses as (

    -- 1..12 without a generator function (portable): the zone lookup always has more than 12 rows.
    select row_number() over (order by location_id) as mes_num from {{ ref('dim_zone') }}

),

calendario as (

    select a.anio, cast(m.mes_num as integer) as mes_num
    from anios as a
    cross join meses as m
    where m.mes_num <= 12

),

cargados as (

    select
        c.anio,
        c.mes_num,
        {{ mes_label('c.anio', 'c.mes_num') }} as mes,
        {{ mes_label('c.anio - 1', 'c.mes_num') }} as mes_anterior,
        a.trips as viajes_mes,
        b.trips as viajes_anterior
    from calendario as c
    left join {{ ref('agg_month_profile') }} as a on a.year = c.anio and a.month = c.mes_num
    left join {{ ref('agg_month_profile') }} as b on b.year = c.anio - 1 and b.month = c.mes_num

)

select
    anio,
    mes_num,
    mes,
    mes_anterior,
    viajes_mes,
    viajes_anterior,
    {{ var_pct('viajes_mes', 'viajes_anterior') }} as variacion_pct,
    case
        when viajes_mes is not null and viajes_anterior is not null then 'comparado'
        when viajes_mes is not null then 'falta el mes del año anterior'
        else 'mes sin cargar'
    end as estado
from cargados
