-- Contexto 6: por año y forma de pago: viajes (todos), viajes con tarifa > 0, cuántos de ellos dejan
-- propina y la propina como % de la tarifa (promedio por viaje y ponderada).
select
    year,
    payment_type,
    count(*) as trips,
    sum(case when fare_amount > 0 then 1 else 0 end) as trips_fare_positive,
    sum(case when fare_amount > 0 and tip_amount > 0 then 1 else 0 end) as trips_with_tip,
    avg(case when fare_amount > 0 then tip_pct end) as avg_tip_pct,
    100.0 * sum(case when fare_amount > 0 then tip_amount else 0 end)
        / nullif(sum(case when fare_amount > 0 then fare_amount else 0 end), 0) as weighted_tip_pct,
    avg(fare_amount) as avg_fare
from marts.fact_trips
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
group by year, payment_type
