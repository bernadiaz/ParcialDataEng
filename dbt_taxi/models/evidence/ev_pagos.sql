-- Grain: one row per comparison and payment type (question 4): weight in the trips and tip as % of the fare (average
-- per trip and weighted, trips with fare > 0 only).
with pagos as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        c.anio_anterior,
        a.payment_type,
        max(case when a.year = c.anio then a.trips end) as viajes_mes,
        max(case when a.year = c.anio_anterior then a.trips end) as viajes_anterior,
        max(case when a.year = c.anio then a.trips_fare_positive end) as viajes_tarifa_positiva_mes,
        max(case when a.year = c.anio_anterior then a.trips_fare_positive end) as viajes_tarifa_positiva_anterior,
        max(case when a.year = c.anio then a.trips_with_tip end) as viajes_con_propina_mes,
        max(case when a.year = c.anio_anterior then a.trips_with_tip end) as viajes_con_propina_anterior,
        max(case when a.year = c.anio then a.avg_tip_pct end) as propina_media_pct_mes,
        max(case when a.year = c.anio_anterior then a.avg_tip_pct end) as propina_media_pct_anterior,
        max(case when a.year = c.anio then a.weighted_tip_pct end) as propina_ponderada_pct_mes,
        max(case when a.year = c.anio_anterior then a.weighted_tip_pct end) as propina_ponderada_pct_anterior
    from {{ ref('ev_comparaciones') }} as c
    inner join {{ ref('agg_payment_month') }} as a on a.month = c.mes_num and a.year in (c.anio, c.anio_anterior)
    group by c.mes, c.anio, c.mes_num, c.anio_anterior, a.payment_type

)

select
    g.mes,
    g.anio,
    g.mes_num,
    g.payment_type,
    {{ payment_label('g.payment_type') }} as forma_pago,
    g.viajes_mes,
    g.viajes_anterior,
    {{ pct_of('g.viajes_mes', 'm.trips') }} as participacion_mes_pct,
    {{ pct_of('g.viajes_anterior', 'b.trips') }} as participacion_anterior_pct,
    g.viajes_tarifa_positiva_mes,
    g.viajes_tarifa_positiva_anterior,
    {{ pct_of('g.viajes_con_propina_mes', 'g.viajes_tarifa_positiva_mes') }} as pct_con_propina_mes,
    {{ pct_of('g.viajes_con_propina_anterior', 'g.viajes_tarifa_positiva_anterior') }} as pct_con_propina_anterior,
    g.propina_media_pct_mes,
    g.propina_media_pct_anterior,
    g.propina_ponderada_pct_mes,
    g.propina_ponderada_pct_anterior
from pagos as g
inner join {{ ref('agg_month_profile') }} as m on m.year = g.anio and m.month = g.mes_num
inner join {{ ref('agg_month_profile') }} as b on b.year = g.anio_anterior and b.month = g.mes_num
