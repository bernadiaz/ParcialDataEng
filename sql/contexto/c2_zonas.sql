-- Contexto 2: pickups por zona y año (todas las zonas). Primero agrega agg_zone_hour por zona y después
-- une dim_zone (265 filas): el JOIN trabaja sobre cientos de filas y no sobre el detalle por hora.
with by_zone as (
    select year, pu_location_id, sum(trips) as trips
    from marts.agg_zone_hour
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year, pu_location_id
)
select b.year, b.pu_location_id, z.zone, z.borough, b.trips
from by_zone as b
inner join marts.dim_zone as z on z.location_id = b.pu_location_id
