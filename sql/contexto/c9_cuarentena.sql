-- Contexto 9 (respaldo): filas aceptadas (fact_trips) y en cuarentena (raw.yellow_quarantine) por año,
-- desde el warehouse. Se usa solo si la base de control local no tiene el reporte de calidad del mes.
with accepted as (
    select year, count(*) as accepted
    from marts.fact_trips
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year
),
quarantined as (
    select year, count(*) as quarantined
    from raw.yellow_quarantine
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year
)
select a.year, a.accepted, coalesce(q.quarantined, 0) as quarantined
from accepted as a
left join quarantined as q on q.year = a.year
