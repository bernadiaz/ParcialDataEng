-- Contexto 5: peaje de congestión (CBD) por día: viajes, viajes con cbd_congestion_fee > 0 y viajes
-- donde la columna trae un valor (NULL = la columna no existía en el archivo de ese mes).
select
    year,
    pickup_date,
    count(*) as trips,
    sum(case when cbd_congestion_fee > 0 then 1 else 0 end) as trips_with_cbd_fee,
    count(cbd_congestion_fee) as cbd_fee_reported
from marts.fact_trips
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
group by year, pickup_date
