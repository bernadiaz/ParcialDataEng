-- Contexto 4: calendario. Por año y día de la semana: cuántas veces aparece ese día en el mes
-- (dim_date) y cuántos viajes tuvo. Agrega agg_zone_hour por fecha antes de unir dim_date.
with by_day as (
    select year, pickup_date, sum(trips) as trips
    from marts.agg_zone_hour
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year, pickup_date
),
calendar as (
    select year, day_of_week_iso, count(*) as days
    from marts.dim_date
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year, day_of_week_iso
),
trips_by_dow as (
    select d.year, d.day_of_week_iso, sum(b.trips) as trips
    from by_day as b
    inner join marts.dim_date as d on d.date_key = b.pickup_date
    group by d.year, d.day_of_week_iso
)
select c.year, c.day_of_week_iso, c.days, coalesce(t.trips, 0) as trips
from calendar as c
left join trips_by_dow as t on t.year = c.year and t.day_of_week_iso = c.day_of_week_iso
