-- Grain: one row per comparison and borough (question 1). razon = trips of the month / trips a year before.
with por_borough as (

    select
        mes,
        anio,
        mes_num,
        borough,
        cast(sum(viajes_mes) as bigint) as viajes_mes,
        cast(sum(viajes_anterior) as bigint) as viajes_anterior
    from {{ ref('ev_zonas') }}
    group by mes, anio, mes_num, borough

),

totales as (

    select mes, sum(viajes_mes) as total_mes, sum(viajes_anterior) as total_anterior
    from por_borough
    group by mes

)

select
    b.mes,
    b.anio,
    b.mes_num,
    b.borough,
    b.viajes_mes,
    b.viajes_anterior,
    b.viajes_mes - b.viajes_anterior as variacion,
    {{ var_pct('b.viajes_mes', 'b.viajes_anterior') }} as variacion_pct,
    cast(b.viajes_mes as double) / nullif(cast(b.viajes_anterior as double), 0) as razon,
    {{ pct_of('b.viajes_mes', 't.total_mes') }} as participacion_mes_pct,
    {{ pct_of('b.viajes_anterior', 't.total_anterior') }} as participacion_anterior_pct
from por_borough as b
inner join totales as t on t.mes = b.mes
