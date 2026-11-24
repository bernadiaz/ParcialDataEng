-- Grain: one row per comparison, period and rank (1..3): the highest fares above var('fare_cap') with their route,
-- distance and payment type (questions 2, 5 and 6, and the conclusion about outliers).
select
    p.mes,
    p.anio,
    p.mes_num,
    p.periodo,
    p.rol,
    cast(t.rank_in_month as integer) as puesto,
    t.fare_amount as tarifa,
    t.total_amount as total_cobrado,
    t.trip_distance as distancia_millas,
    cast(t.pickup_hour as integer) as hora,
    {{ payment_label('t.payment_type') }} as forma_pago,
    pu.zone as zona_origen,
    dz.zone as zona_destino
from {{ ref('ev_periodos') }} as p
inner join {{ ref('top_fare_trips') }} as t on t.year = p.anio_periodo and t.month = p.mes_num
left join {{ ref('dim_zone') }} as pu on pu.location_id = t.pu_location_id
left join {{ ref('dim_zone') }} as dz on dz.location_id = t.do_location_id
