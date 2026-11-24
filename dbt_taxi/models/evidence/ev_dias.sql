-- Grain: one row per comparison, period and day (questions 3 and 6). pct_con_peaje is NULL, not 0, when the file
-- of that month had no cbd_congestion_fee column.
select
    p.mes,
    p.anio,
    p.mes_num,
    p.periodo,
    p.rol,
    d.pickup_date as fecha,
    cast(extract(day from d.pickup_date) as integer) as dia,
    d.trips as viajes,
    d.revenue as recaudacion,
    d.trips_with_cbd_fee as viajes_con_peaje,
    case when d.cbd_fee_reported > 0 then {{ pct_of('d.trips_with_cbd_fee', 'd.trips') }} end as pct_con_peaje
from {{ ref('ev_periodos') }} as p
inner join {{ ref('agg_day') }} as d on d.year = p.anio_periodo and d.month = p.mes_num
