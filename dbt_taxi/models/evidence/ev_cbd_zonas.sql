-- Grain: one row per comparison and pickup zone with var('cbd_min_zone_trips') trips or more in the month
-- (question 3): share of trips with cbd_congestion_fee > 0 and, for the conclusions, how the trips of that zone
-- changed against the previous year. Same ranking rule as sql/q3_cbd_fee_share.sql.
with zonas as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        z.pu_location_id,
        z.trips as viajes,
        z.trips_with_cbd_fee as viajes_con_peaje,
        {{ pct_of('z.trips_with_cbd_fee', 'z.trips') }} as pct_con_peaje,
        cast(row_number() over (
            partition by c.mes order by 1.0 * z.trips_with_cbd_fee / z.trips desc, z.trips desc, z.pu_location_id
        ) as integer) as puesto
    from {{ ref('ev_comparaciones') }} as c
    inner join {{ ref('agg_zone_month') }} as z on z.year = c.anio and z.month = c.mes_num
    where z.trips >= {{ var('cbd_min_zone_trips') }}

)

select
    z.mes,
    z.anio,
    z.mes_num,
    z.puesto,
    e.zona,
    e.borough,
    z.viajes,
    z.viajes_con_peaje,
    z.pct_con_peaje,
    e.viajes_anterior,
    e.variacion_pct as variacion_viajes_pct
from zonas as z
inner join {{ ref('ev_zonas') }} as e on e.mes = z.mes and e.pu_location_id = z.pu_location_id
