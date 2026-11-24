-- Contexto 2: pickups por zona y año (todas las zonas), de marts.agg_zone_month (una fila por zona y mes).
select a.year, a.pu_location_id, z.zone, z.borough, a.trips
from marts.agg_zone_month as a
inner join marts.dim_zone as z on z.location_id = a.pu_location_id
where a.month = ${MONTH} and a.year in (${YEAR}, ${CMP_YEAR})
