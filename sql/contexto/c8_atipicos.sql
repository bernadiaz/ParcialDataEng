-- Contexto 8: los 3 viajes con mayor tarifa de cada mes entre los que superan el tope de ${FARE_CAP} USD, con sus zonas.
select
    t.year, t.rank_in_month, t.fare_amount, t.total_amount, t.trip_distance, t.payment_type, t.pickup_hour,
    pu.zone as pu_zone, dz.zone as do_zone
from marts.top_fare_trips as t
left join marts.dim_zone as pu on pu.location_id = t.pu_location_id
left join marts.dim_zone as dz on dz.location_id = t.do_location_id
where t.month = ${MONTH} and t.year in (${YEAR}, ${CMP_YEAR}) and t.fare_amount > ${FARE_CAP}
