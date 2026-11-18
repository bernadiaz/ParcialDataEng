-- Contexto 7: viajes que empiezan o terminan en JFK o LaGuardia (misma definición que Q5): totales por
-- aeropuerto, tarifa media, mediana, media sin atípicos (fare_amount > ${FARE_CAP}), tarifa máxima y
-- la mediana de la tarifa fija de JFK (RatecodeID 2).
with airports as (
    select location_id, zone from marts.dim_zone where zone in ('JFK Airport', 'LaGuardia Airport')
),
trips as (
    select f.year, f.fare_amount, f.ratecode_id, pa.zone as pu_airport, da.zone as do_airport
    from marts.fact_trips as f
    left join airports as pa on pa.location_id = f.pu_location_id
    left join airports as da on da.location_id = f.do_location_id
    where f.month = ${MONTH} and f.year in (${YEAR}, ${CMP_YEAR})
      and (pa.location_id is not null or da.location_id is not null)
)
select
    year,
    count(*) as airport_trips,
    sum(case when pu_airport = 'JFK Airport' or do_airport = 'JFK Airport' then 1 else 0 end) as jfk_trips,
    sum(case when pu_airport = 'LaGuardia Airport' or do_airport = 'LaGuardia Airport' then 1 else 0 end) as lga_trips,
    sum(case when pu_airport is not null then 1 else 0 end) as pickups_at_airport,
    avg(fare_amount) as avg_fare,
    median(fare_amount) as median_fare,
    avg(case when fare_amount <= ${FARE_CAP} then fare_amount end) as avg_fare_capped,
    max(fare_amount) as max_fare,
    median(case when ratecode_id = 2 then fare_amount end) as jfk_flat_fare
from trips
group by year
