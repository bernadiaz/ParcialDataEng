-- Grain: one row per comparison and pickup zone with trips in either month (question 1 and conclusions).
-- puesto_mes / puesto_anterior: rank by trips in each month (NULL = no trips that month). puesto_aporte: rank by how
-- much the zone moves the total in the direction it moved (1 = the zone that adds the most trips when the city grows,
-- or loses the most when it falls; NULL = no trips in the comparison month).
with pickups as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        z.pu_location_id,
        cast(sum(case when z.year = c.anio then z.trips else 0 end) as bigint) as viajes_mes,
        cast(sum(case when z.year = c.anio_anterior then z.trips else 0 end) as bigint) as viajes_anterior
    from {{ ref('ev_comparaciones') }} as c
    inner join {{ ref('agg_zone_month') }} as z on z.month = c.mes_num and z.year in (c.anio, c.anio_anterior)
    group by c.mes, c.anio, c.mes_num, z.pu_location_id

),

ordenados as (

    select
        pickups.*,
        sum(viajes_mes) over (partition by mes) as total_mes,
        sum(viajes_anterior) over (partition by mes) as total_anterior,
        row_number() over (partition by mes order by viajes_mes desc, pu_location_id) as orden_mes,
        row_number() over (partition by mes order by viajes_anterior desc, pu_location_id) as orden_anterior
    from pickups

),

aportes as (

    select
        mes,
        pu_location_id,
        row_number() over (
            partition by mes
            order by (viajes_mes - viajes_anterior) * (case when total_mes >= total_anterior then 1 else -1 end) desc, pu_location_id
        ) as puesto_aporte
    from ordenados
    where viajes_anterior > 0

)

select
    o.mes,
    o.anio,
    o.mes_num,
    o.pu_location_id,
    {{ zone_label('o.pu_location_id', 'd.zone') }} as zona,
    coalesce(d.borough, 'Unknown') as borough,
    case when o.viajes_mes > 0 then cast(o.orden_mes as integer) end as puesto_mes,
    case when o.viajes_anterior > 0 then cast(o.orden_anterior as integer) end as puesto_anterior,
    o.viajes_mes,
    o.viajes_anterior,
    o.viajes_mes - o.viajes_anterior as variacion,
    abs(o.viajes_mes - o.viajes_anterior) as variacion_abs,
    {{ var_pct('o.viajes_mes', 'o.viajes_anterior') }} as variacion_pct,
    {{ pct_of('o.viajes_mes', 'o.total_mes') }} as participacion_mes_pct,
    {{ pct_of('o.viajes_anterior', 'o.total_anterior') }} as participacion_anterior_pct,
    cast(a.puesto_aporte as integer) as puesto_aporte
from ordenados as o
inner join {{ ref('dim_zone') }} as d on d.location_id = o.pu_location_id
left join aportes as a on a.mes = o.mes and a.pu_location_id = o.pu_location_id
