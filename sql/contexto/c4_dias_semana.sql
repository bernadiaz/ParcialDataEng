-- Contexto 4: calendario. Por año y día de la semana: cuántas veces aparece ese día en el mes (dim_date) y cuántos
-- viajes tuvo (marts.agg_day, una fila por día).
with calendar as (
    select year, day_of_week_iso, count(*) as days
    from marts.dim_date
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year, day_of_week_iso
),
trips_by_dow as (
    select d.year, d.day_of_week_iso, sum(a.trips) as trips
    from marts.agg_day as a
    inner join marts.dim_date as d on d.date_key = a.pickup_date
    where a.month = ${MONTH} and a.year in (${YEAR}, ${CMP_YEAR})
    group by d.year, d.day_of_week_iso
)
select c.year, c.day_of_week_iso, c.days, coalesce(t.trips, 0) as trips
from calendar as c
left join trips_by_dow as t on t.year = c.year and t.day_of_week_iso = c.day_of_week_iso
