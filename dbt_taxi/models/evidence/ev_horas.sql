-- Grain: one row per comparison and pickup hour (question 2). Both months side by side: trips, revenue per trip
-- with and without the fares above var('fare_cap'), weight of the airports, distance, highest fare and rank of
-- the hour by revenue per trip.
with horas as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        cast(h.pickup_hour as integer) as hora,
        max(case when h.year = c.anio then h.trips end) as viajes_mes,
        max(case when h.year = c.anio_anterior then h.trips end) as viajes_anterior,
        max(case when h.year = c.anio then h.revenue_per_trip end) as ingreso_viaje_mes,
        max(case when h.year = c.anio_anterior then h.revenue_per_trip end) as ingreso_viaje_anterior,
        max(case when h.year = c.anio then h.revenue_per_trip_capped end) as ingreso_sin_atipicas_mes,
        max(case when h.year = c.anio_anterior then h.revenue_per_trip_capped end) as ingreso_sin_atipicas_anterior,
        max(case when h.year = c.anio then h.airport_trips end) as viajes_aeropuerto_mes,
        max(case when h.year = c.anio_anterior then h.airport_trips end) as viajes_aeropuerto_anterior,
        max(case when h.year = c.anio then h.avg_distance end) as distancia_media_mes,
        max(case when h.year = c.anio_anterior then h.avg_distance end) as distancia_media_anterior,
        max(case when h.year = c.anio then h.max_fare end) as tarifa_maxima_mes,
        max(case when h.year = c.anio_anterior then h.max_fare end) as tarifa_maxima_anterior
    from {{ ref('ev_comparaciones') }} as c
    inner join {{ ref('agg_hour_month') }} as h on h.month = c.mes_num and h.year in (c.anio, c.anio_anterior)
    group by c.mes, c.anio, c.mes_num, h.pickup_hour

)

select
    horas.*,
    {{ var_pct('ingreso_viaje_mes', 'ingreso_viaje_anterior') }} as variacion_ingreso_pct,
    {{ pct_of('viajes_aeropuerto_mes', 'viajes_mes') }} as pct_aeropuerto_mes,
    {{ pct_of('viajes_aeropuerto_anterior', 'viajes_anterior') }} as pct_aeropuerto_anterior,
    case when ingreso_viaje_mes is not null
        then cast(row_number() over (partition by mes order by ingreso_viaje_mes desc nulls last, hora) as integer)
    end as puesto_mes,
    case when ingreso_viaje_anterior is not null
        then cast(row_number() over (partition by mes order by ingreso_viaje_anterior desc nulls last, hora) as integer)
    end as puesto_anterior
from horas
