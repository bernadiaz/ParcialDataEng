# Resultados: diciembre 2025 vs diciembre 2024

> En diciembre 2025 los taxis amarillos hicieron 4.049.994 viajes válidos, +14,9 % que en diciembre 2024 (3.526.288), con una recaudación de US$ 127,1 M (+23,0 %).

| | |
|---|---|
| Comando | `make all MES=2025-12 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-12.parquet` y `yellow_tripdata_2024-12.parquet` |
| Corrida | `20261118T045124Z-6f64c3`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=12/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-12 | `yellow_tripdata_2025-12.parquet` | 4.305.006 | 4.305.006 | 4.049.994 | 255.012 | 5,92 % | 1.107.479 (25,73 %) | sí |
| 2024-12 | `yellow_tripdata_2024-12.parquet` | 3.668.371 | 3.668.371 | 3.526.288 | 142.083 | 3,87 % | 330.384 (9,01 %) | sí |

| regla | severidad | qué controla | 2025-12 | 2024-12 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 9 (0,00 %) | 34 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 58.021 (1,35 %) | 1.223 (0,03 %) | +1,31 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 152.853 (3,55 %) | 75.579 (2,06 %) | +1,49 pp |
| R04 | reject | Total cobrado faltante o negativo. | 48.869 (1,14 %) | 70.496 (1,92 %) | −0,79 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.214.309 (28,21 %) | 356.688 (9,72 %) | +18,48 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 53.451 (1,24 %) | 83.686 (2,28 %) | −1,04 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.150 (0,03 %) | 1.063 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 33.050 (0,77 %) | 0 (0,00 %) | +0,77 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,87 % al 5,92 % de las filas leídas (255.012 filas en diciembre 2025 y 142.083 en diciembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,55 % contra 2,06 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,35 % contra 0,03 %).
- Las reglas de advertencia no sacan filas: 1.107.479 filas aceptadas de diciembre 2025 (25,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 28,2 %, contra 9,7 % en diciembre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de diciembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de diciembre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

## 1. Top 10 de zonas de pickup del mes asignado y su variación contra el mismo mes del año anterior

Consulta: [`sql/q1_top10_pickup_zones.sql`](../../sql/q1_top10_pickup_zones.sql)

<details><summary>SQL</summary>

```sql
-- Q1: Top 10 pickup zones by trips in the assigned month, and their change vs the same month of the previous year.
-- Source: marts.agg_zone_hour (pre-aggregated: scans far fewer rows than fact_trips).
-- Grouped by location_id because zone names are not unique.
with by_zone as (
    select
        pu_location_id,
        sum(case when year = ${YEAR} then trips end) as trips_assigned,
        sum(case when year = ${CMP_YEAR} then trips end) as trips_comparison
    from marts.agg_zone_hour
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by pu_location_id
)
select
    z.borough,
    z.zone as pickup_zone,
    b.trips_assigned,
    b.trips_comparison,
    b.trips_assigned - b.trips_comparison as trips_change,
    round(100.0 * (b.trips_assigned - b.trips_comparison) / nullif(b.trips_comparison, 0), 2) as trips_change_pct
from by_zone as b
inner join marts.dim_zone as z on z.location_id = b.pu_location_id
order by b.trips_assigned desc nulls last
limit 10
```

</details>

| borough | pickup_zone | trips_assigned | trips_comparison | trips_change | trips_change_pct |
|---|---|---|---|---|---|
| Manhattan | Upper East Side South | 185.995 | 178.797 | 7.198 | 4,03 |
| Manhattan | Upper East Side North | 167.419 | 159.600 | 7.819 | 4,90 |
| Manhattan | Midtown Center | 154.076 | 154.573 | -497 | -0,32 |
| Queens | JFK Airport | 152.146 | 151.263 | 883 | 0,58 |
| Manhattan | Penn Station/Madison Sq West | 128.426 | 126.949 | 1.477 | 1,16 |
| Manhattan | Lincoln Square East | 126.735 | 122.871 | 3.864 | 3,14 |
| Manhattan | Midtown East | 124.797 | 123.888 | 909 | 0,73 |
| Manhattan | Times Sq/Theatre District | 115.045 | 118.559 | -3.514 | -2,96 |
| Manhattan | Upper West Side South | 107.236 | 104.346 | 2.890 | 2,77 |
| Manhattan | Union Sq | 106.524 | 96.830 | 9.694 | 10,01 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, ocho crecen (entre +0,6 % en JFK Airport y +10,0 % en Union Sq), una cae (Times Sq/Theatre District −3,0 %) y una se mantiene. Upper East Side South lidera con 185.995 viajes (+4,0 %). Respecto de diciembre 2024 entran al top 10 Upper West Side South y Union Sq y salen LaGuardia Airport y Midtown North. En los aeropuertos, JFK (puesto 4 del top) crece +0,6 % y LaGuardia (fuera del top) cae −5,2 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 33,8 % de los pickups, frente al 38,4 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (10.250 → 37.334), aunque sobre una base chica, contra +14,9 % del total.

## 2. Hora del día con mayor ingreso promedio por viaje (total_amount), en cada uno de los dos meses

Consulta: [`sql/q2_peak_revenue_hour.sql`](../../sql/q2_peak_revenue_hour.sql)

<details><summary>SQL</summary>

```sql
-- Q2: Hour of the day with the highest average revenue per trip (revenue = total_amount), for each of the two months.
-- Source: marts.agg_zone_hour; average per trip = sum(total_revenue) / sum(trips).
with by_hour as (
    select
        year,
        month,
        pickup_hour,
        sum(trips) as trips,
        round(sum(total_revenue) / sum(trips), 2) as avg_revenue_per_trip
    from marts.agg_zone_hour
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year, month, pickup_hour
),
ranked as (
    select by_hour.*, row_number() over (partition by year order by avg_revenue_per_trip desc) as rank_in_month
    from by_hour
)
select year, month, pickup_hour, trips, avg_revenue_per_trip
from ranked
where rank_in_month = 1
order by year desc
```

</details>

| year | month | pickup_hour | trips | avg_revenue_per_trip |
|---|---|---|---|---|
| 2025 | 12 | 5 | 33.884 | 36,68 |
| 2024 | 12 | 5 | 20.665 | 40,15 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,68 en 2025 y US$ 40,15 en 2024. Es una hora de poco volumen (33.884 viajes, contra 251.670 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 15,5 % de sus viajes toca JFK o LaGuardia (contra 7,9 % en todo el mes) y la distancia media es de 6,09 millas (contra 3,52). En 2025 los viajes de aeropuerto son menos (del 27,8 % al 15,5 % de los viajes de las 5:00) y la distancia media baja (de 6,55 a 6,09 millas), por eso el ingreso por viaje cae un 8,6 %.

## 3. Proporción de viajes con cbd_congestion_fee > 0 en el mes asignado y las 5 zonas de pickup con mayor proporción

Consulta: [`sql/q3_cbd_fee_share.sql`](../../sql/q3_cbd_fee_share.sql)

<details><summary>SQL</summary>

```sql
-- Q3: Share of trips with cbd_congestion_fee > 0 in the assigned month, and the 5 pickup zones with the highest share.
-- Zones need at least 1,000 trips in the month so a zone with a handful of trips cannot top the list at 100%.
-- First row = all zones; next rows = top 5 zones.
with by_zone as (
    select
        f.pu_location_id,
        count(*) as trips,
        sum(case when f.cbd_congestion_fee > 0 then 1 else 0 end) as trips_with_cbd_fee
    from marts.fact_trips as f
    where f.year = ${YEAR} and f.month = ${MONTH}
    group by f.pu_location_id
),
overall as (
    select
        0 as sort_order,
        'ALL ZONES' as scope,
        cast(null as varchar) as borough,
        sum(trips) as trips,
        sum(trips_with_cbd_fee) as trips_with_cbd_fee,
        round(100.0 * sum(trips_with_cbd_fee) / sum(trips), 2) as pct_with_cbd_fee
    from by_zone
),
top_zones as (
    select
        row_number() over (order by 1.0 * b.trips_with_cbd_fee / b.trips desc, b.trips desc) as sort_order,
        z.zone as scope,
        z.borough,
        b.trips,
        b.trips_with_cbd_fee,
        round(100.0 * b.trips_with_cbd_fee / b.trips, 2) as pct_with_cbd_fee
    from by_zone as b
    inner join marts.dim_zone as z on z.location_id = b.pu_location_id
    where b.trips >= 1000
)
select scope, borough, trips, trips_with_cbd_fee, pct_with_cbd_fee
from (
    select * from overall
    union all
    select * from top_zones where sort_order <= 5
) as result
order by sort_order
```

</details>

| scope | borough | trips | trips_with_cbd_fee | pct_with_cbd_fee |
|---|---|---|---|---|
| ALL ZONES |  | 4.049.994 | 2.918.819 | 72,07 |
| SoHo | Manhattan | 33.313 | 33.228 | 99,74 |
| Greenwich Village South | Manhattan | 56.945 | 56.774 | 99,70 |
| West Village | Manhattan | 84.522 | 84.205 | 99,62 |
| East Village | Manhattan | 99.393 | 98.936 | 99,54 |
| Little Italy/NoLiTa | Manhattan | 44.885 | 44.675 | 99,53 |

**Interpretación:** El 72,07 % de los viajes de diciembre 2025 pagó cbd_congestion_fee (2.918.819 de 4.049.994, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Little Italy/NoLiTa, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En diciembre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 33.050 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

## 4. Propina promedio como % de la tarifa, por forma de pago (los dos meses)

Consulta: [`sql/q4_tip_pct_by_payment.sql`](../../sql/q4_tip_pct_by_payment.sql)

<details><summary>SQL</summary>

```sql
-- Q4: Average tip as a percentage of the fare, by payment type (both months).
-- tip_pct = 100 * tip_amount / fare_amount, only for fare_amount > 0. The weighted figure
-- (sum of tips / sum of fares) is also shown because it is less sensitive to very small fares.
select
    year,
    month,
    payment_type,
    case payment_type
        when 0 then 'Flex Fare'
        when 1 then 'Credit card'
        when 2 then 'Cash'
        when 3 then 'No charge'
        when 4 then 'Dispute'
        when 5 then 'Unknown'
        when 6 then 'Voided trip'
    end as payment_type_name,
    count(*) as trips,
    round(avg(tip_pct), 2) as avg_tip_pct,
    round(100.0 * sum(tip_amount) / sum(fare_amount), 2) as weighted_tip_pct
from marts.fact_trips
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR}) and fare_amount > 0
group by year, month, payment_type
order by year desc, payment_type
```

</details>

| year | month | payment_type | payment_type_name | trips | avg_tip_pct | weighted_tip_pct |
|---|---|---|---|---|---|---|
| 2025 | 12 | 0 | Flex Fare | 1.084.771 | 2,01 | 1,75 |
| 2025 | 12 | 1 | Credit card | 2.545.696 | 24,80 | 21,25 |
| 2025 | 12 | 2 | Cash | 372.921 | 0,00 | 0,00 |
| 2025 | 12 | 3 | No charge | 11.304 | 0,01 | 0,00 |
| 2025 | 12 | 4 | Dispute | 33.959 | 0,00 | 0,00 |
| 2024 | 12 | 0 | Flex Fare | 289.128 | 5,40 | 5,67 |
| 2024 | 12 | 1 | Credit card | 2.708.226 | 24,93 | 22,17 |
| 2024 | 12 | 2 | Cash | 462.843 | 0,00 | 0,00 |
| 2024 | 12 | 3 | No charge | 15.055 | 0,08 | 0,03 |
| 2024 | 12 | 4 | Dispute | 42.308 | 0,03 | 0,04 |

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 24,80 % de la tarifa en 2025 frente a 24,93 % en 2024 (21,3 % y 22,2 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 8,4 % al 26,8 % de los viajes (289.128 → 1.084.771 con tarifa > 0) y cuya propina cae del 5,40 % al 2,01 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 9,7 % al 28,2 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 76,8 % al 62,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

## 5. Viajes que empiezan o terminan en JFK o LaGuardia y su tarifa promedio

Consulta: [`sql/q5_airport_trips.sql`](../../sql/q5_airport_trips.sql)

<details><summary>SQL</summary>

```sql
-- Q5: Trips and average fare of trips that start or end at JFK or LaGuardia, identified by zone name.
-- A trip between both airports is counted once (OR, not a union).
select
    f.year,
    f.month,
    count(*) as airport_trips,
    round(avg(f.fare_amount), 2) as avg_fare_amount,
    sum(case when pu.zone = 'JFK Airport' or dz.zone = 'JFK Airport' then 1 else 0 end) as trips_touching_jfk,
    sum(case when pu.zone = 'LaGuardia Airport' or dz.zone = 'LaGuardia Airport' then 1 else 0 end) as trips_touching_lga
from marts.fact_trips as f
inner join marts.dim_zone as pu on pu.location_id = f.pu_location_id
inner join marts.dim_zone as dz on dz.location_id = f.do_location_id
where f.month = ${MONTH}
  and f.year in (${YEAR}, ${CMP_YEAR})
  and (pu.zone in ('JFK Airport', 'LaGuardia Airport') or dz.zone in ('JFK Airport', 'LaGuardia Airport'))
group by f.year, f.month
order by f.year desc
```

</details>

| year | month | airport_trips | avg_fare_amount | trips_touching_jfk | trips_touching_lga |
|---|---|---|---|---|---|
| 2025 | 12 | 320.421 | 56,93 | 180.591 | 142.391 |
| 2024 | 12 | 335.512 | 56,92 | 184.294 | 153.875 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 4,5 % (335.512 → 320.421) mientras el total de la ciudad sube un 14,9 %, así que su peso cae del 9,5 % al 7,9 % de los viajes. Por aeropuerto, JFK cae −2,0 % y LaGuardia cae −7,5 %. La tarifa promedio se mantiene (US$ 56,92 → US$ 56,93), y la mediana baja de US$ 58,30 a US$ 57,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

## 6. Variación del total de viajes y de la tarifa promedio entre los dos meses

Consulta: [`sql/q6_yoy_variation.sql`](../../sql/q6_yoy_variation.sql)

<details><summary>SQL</summary>

```sql
-- Q6: Change in total trips and average fare between the assigned month and the same month of the previous year.
with by_month as (
    select year, count(*) as trips, avg(fare_amount) as avg_fare_amount
    from marts.fact_trips
    where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
    group by year
)
select
    a.trips as trips_assigned,
    c.trips as trips_comparison,
    a.trips - c.trips as trips_change,
    round(100.0 * (a.trips - c.trips) / c.trips, 2) as trips_change_pct,
    round(a.avg_fare_amount, 2) as avg_fare_assigned,
    round(c.avg_fare_amount, 2) as avg_fare_comparison,
    round(100.0 * (a.avg_fare_amount - c.avg_fare_amount) / c.avg_fare_amount, 2) as avg_fare_change_pct
from by_month as a
inner join by_month as c on a.year = ${YEAR} and c.year = ${CMP_YEAR}
```

</details>

| trips_assigned | trips_comparison | trips_change | trips_change_pct | avg_fare_assigned | avg_fare_comparison | avg_fare_change_pct |
|---|---|---|---|---|---|---|
| 4.049.994 | 3.526.288 | 523.706 | 14,85 | 22,50 | 20,34 | 10,65 |

**Interpretación:**

- Diciembre 2025 tuvo 4.049.994 viajes válidos contra 3.526.288 en diciembre 2024: +523.706 viajes (+14,85 %). La recaudación total (total_amount) crece un 23,0 %, de US$ 103,4 M a US$ 127,1 M.
- El calendario casi no influye: diciembre 2025 tuvo 5 miércoles, y diciembre 2024, 5 domingos (días flojos). Todos los días de la semana crecen (por día), entre +9 % y +23 %, así que el aumento es real.
- La tarifa promedio sube un 10,65 % (de US$ 20,34 a US$ 22,50). La mediana pasa de US$ 14,20 a US$ 17,00 (+19,7 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de diciembre 2025 hay más viajes Flex Fare, que son más caros (US$ 27,36 contra US$ 20,72 del resto) y pasan del 8 % al 27 % de los viajes y menos viajes a aeropuertos (del 9,5 % al 7,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 2,7 % (de US$ 20,17 a US$ 20,72). El viaje promedio es más largo: 3,52 contra 3,32 millas.
- Calidad: la cuarentena sube del 3,87 % al 5,92 % de las filas leídas (255.012 filas en diciembre 2025 y 142.083 en diciembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,55 % contra 2,06 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,35 % contra 0,03 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en diciembre 2025 (+14,9 % de viajes, +23,0 % de recaudación). Las zonas que más suman viajes son East Village (+29,4 %), Kips Bay (+33,7 %) y East Harlem South (+56,6 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 72,1 % de los viajes de diciembre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +11,7 %, Greenwich Village South +12,7 % y West Village +12,0 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,52 contra 3,32 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 17,00). La propina con tarjeta no se mueve (24,9 % → 24,8 %).
- Hay 38 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 3.033,10, en 2024) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (diciembre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 5,92 % y del 3,87 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-12 INGEST_MODE=direct WAREHOUSE=duckdb`.
