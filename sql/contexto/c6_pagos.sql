-- Contexto 6: por año y forma de pago: viajes (todos), viajes con tarifa > 0, cuántos de ellos dejan propina y la
-- propina como % de la tarifa (promedio por viaje y ponderada).
select year, payment_type, trips, trips_fare_positive, trips_with_tip, avg_tip_pct, weighted_tip_pct, avg_fare
from marts.agg_payment_month
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
