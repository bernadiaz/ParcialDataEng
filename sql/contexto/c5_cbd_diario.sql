-- Contexto 5: peaje de congestión (CBD) por día: viajes, viajes con cbd_congestion_fee > 0 y viajes donde la columna
-- trae un valor (NULL = la columna no existía en el archivo de ese mes).
select year, pickup_date, trips, trips_with_cbd_fee, cbd_fee_reported
from marts.agg_day
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
