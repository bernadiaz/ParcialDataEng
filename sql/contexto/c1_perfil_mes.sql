-- Contexto 1: perfil de cada mes (volumen, ingresos, tarifas, distancia, mezcla de pagos y peaje CBD).
-- Lo usa src/interpretacion.py para redactar las interpretaciones; no es una pregunta del examen.
-- ${FARE_CAP}: tope del promedio "sin atípicos" (ninguna regla de calidad limita la tarifa).
select
    f.year,
    count(*) as trips,
    sum(f.total_amount) as revenue,
    avg(f.fare_amount) as avg_fare,
    median(f.fare_amount) as median_fare,
    avg(case when f.fare_amount <= ${FARE_CAP} then f.fare_amount end) as avg_fare_capped,
    sum(case when f.fare_amount > ${FARE_CAP} then 1 else 0 end) as fares_over_cap,
    max(f.fare_amount) as max_fare,
    avg(f.trip_distance) as avg_distance,
    100.0 * sum(case when f.trip_distance > 10 then 1 else 0 end) / count(*) as pct_long_trips,
    avg(f.duration_min) as avg_duration_min,
    sum(case when f.payment_type = 0 then 1 else 0 end) as flex_trips,
    avg(case when f.payment_type = 0 then f.fare_amount end) as avg_fare_flex,
    avg(case when f.payment_type <> 0 then f.fare_amount end) as avg_fare_not_flex,
    avg(case when f.payment_type = 0 and f.fare_amount <= ${FARE_CAP} then f.fare_amount end) as avg_fare_flex_capped,
    avg(case when f.payment_type <> 0 and f.fare_amount <= ${FARE_CAP} then f.fare_amount end) as avg_fare_not_flex_capped,
    sum(case when f.payment_type = 1 then 1 else 0 end) as card_trips,
    sum(case when f.payment_type = 2 then 1 else 0 end) as cash_trips,
    count(distinct f.pickup_date) as days_with_trips,
    count(f.cbd_congestion_fee) as cbd_fee_reported,
    sum(case when f.cbd_congestion_fee > 0 then 1 else 0 end) as trips_with_cbd_fee,
    avg(case when f.cbd_congestion_fee > 0 then f.cbd_congestion_fee end) as avg_cbd_fee,
    min(case when f.cbd_congestion_fee > 0 then f.cbd_congestion_fee end) as min_cbd_fee,
    max(f.cbd_congestion_fee) as max_cbd_fee
from marts.fact_trips as f
where f.month = ${MONTH} and f.year in (${YEAR}, ${CMP_YEAR})
group by f.year
