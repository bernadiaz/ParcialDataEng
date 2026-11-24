-- Contexto 3: por año y hora de pickup: volumen, ingreso por viaje, peso de los aeropuertos (JFK o LaGuardia en
-- el origen o el destino), distancia media, ingreso por viaje sin tarifas atípicas y la tarifa máxima.
select year, pickup_hour, trips, revenue_per_trip, airport_trips, avg_distance, revenue_per_trip_capped, max_fare
from marts.agg_hour_month
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
