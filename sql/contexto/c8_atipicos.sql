-- Contexto 8: los 3 viajes con mayor tarifa de cada mes entre los que superan ${FARE_CAP}, con sus zonas.
-- Filtra antes de numerar (son pocas filas) y une dim_zone solo para esas filas.
with ranked as (
    select
        f.year, f.fare_amount, f.total_amount, f.trip_distance, f.payment_type, f.pickup_hour,
        f.pu_location_id, f.do_location_id,
        row_number() over (partition by f.year order by f.fare_amount desc) as rank_in_month
    from marts.fact_trips as f
    where f.month = ${MONTH} and f.year in (${YEAR}, ${CMP_YEAR}) and f.fare_amount > ${FARE_CAP}
)
select
    r.year, r.rank_in_month, r.fare_amount, r.total_amount, r.trip_distance, r.payment_type, r.pickup_hour,
    pu.zone as pu_zone, dz.zone as do_zone
from ranked as r
left join marts.dim_zone as pu on pu.location_id = r.pu_location_id
left join marts.dim_zone as dz on dz.location_id = r.do_location_id
where r.rank_in_month <= 3
