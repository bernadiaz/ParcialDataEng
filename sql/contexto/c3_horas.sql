-- Contexto 3: por año y hora de pickup: volumen, ingreso por viaje, peso de los aeropuertos (JFK o
-- LaGuardia en el origen o el destino), distancia media, ingreso por viaje sin tarifas atípicas
-- (fare_amount > ${FARE_CAP}) y la tarifa máxima. Los aeropuertos son 2 ids: LEFT JOIN contra ese
-- conjunto chico en lugar de unir dim_zone completa dos veces.
with airports as (
    select location_id from marts.dim_zone where zone in ('JFK Airport', 'LaGuardia Airport')
)
select
    f.year,
    f.pickup_hour,
    count(*) as trips,
    sum(f.total_amount) / count(*) as revenue_per_trip,
    sum(case when pa.location_id is not null or da.location_id is not null then 1 else 0 end) as airport_trips,
    avg(f.trip_distance) as avg_distance,
    sum(case when f.fare_amount <= ${FARE_CAP} then f.total_amount end)
        / nullif(sum(case when f.fare_amount <= ${FARE_CAP} then 1 else 0 end), 0) as revenue_per_trip_capped,
    max(f.fare_amount) as max_fare
from marts.fact_trips as f
left join airports as pa on pa.location_id = f.pu_location_id
left join airports as da on da.location_id = f.do_location_id
where f.month = ${MONTH} and f.year in (${YEAR}, ${CMP_YEAR})
group by f.year, f.pickup_hour
