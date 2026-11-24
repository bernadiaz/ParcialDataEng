# Resultados: diciembre 2025 vs diciembre 2024

> En diciembre 2025 los taxis amarillos hicieron 4.049.994 viajes válidos, +14,9 % que en diciembre 2024 (3.526.288), con una recaudación de US$ 127,1 M (+23,0 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-12 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-12.parquet` y `yellow_tripdata_2024-12.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-12`](http://localhost:8090/superset/dashboard/respaldo-local-2025-12/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=12/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-12 | `yellow_tripdata_2025-12.parquet` | 4.305.006 | 4.305.006 | 4.049.994 | 255.012 | 5,92 % | 1.107.479 (25,73 %) | sí |
| 2024-12 | `yellow_tripdata_2024-12.parquet` | 3.668.371 | 3.668.371 | 3.526.288 | 142.083 | 3,87 % | 330.384 (9,01 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

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

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 3,87 % al 5,92 % de las filas leídas (255.012 filas en diciembre 2025 y 142.083 en diciembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,55 % contra 2,06 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,35 % contra 0,03 %).
- Las reglas de advertencia no sacan filas: 1.107.479 filas aceptadas de diciembre 2025 (25,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 28,2 %, contra 9,7 % en diciembre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de diciembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de diciembre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

**Respaldo en Superset:** [EC.4 Contrato de esquema: novedades de cada archivo][EC.4]

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

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, ocho crecen (entre +0,6 % en JFK Airport y +10,0 % en Union Sq), una cae (Times Sq/Theatre District −3,0 %) y una se mantiene. Upper East Side South lidera con 185.995 viajes (+4,0 %). Respecto de diciembre 2024 entran al top 10 Upper West Side South y Union Sq y salen LaGuardia Airport y Midtown North. En los aeropuertos, JFK (puesto 4 del top) crece +0,6 % y LaGuardia (fuera del top) cae −5,2 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 33,8 % de los pickups, frente al 38,4 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (10.250 → 37.334), aunque sobre una base chica, contra +14,9 % del total.

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1] · [E1.3 Top 10 del mismo mes del año anterior][E1.3] · [E1.4 Concentración y composición del top 10][E1.4] · [E1.5 Pickups en JFK y LaGuardia][E1.5] · [E1.6 Pickups por borough][E1.6]

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

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,68 en 2025 y US$ 40,15 en 2024. Es una hora de poco volumen (33.884 viajes, contra 251.670 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 15,5 % de sus viajes toca JFK o LaGuardia (contra 7,9 % en todo el mes) y la distancia media es de 6,09 millas (contra 3,52). En 2025 los viajes de aeropuerto son menos (del 27,8 % al 15,5 % de los viajes de las 5:00) y la distancia media baja (de 6,55 a 6,09 millas), por eso el ingreso por viaje cae un 8,6 %.

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1] · [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5] · [E2.6 Las 24 horas: viajes de aeropuerto y distancia media][E2.6] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]

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

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 72,07 % de los viajes de diciembre 2025 pagó cbd_congestion_fee (2.918.819 de 4.049.994, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Little Italy/NoLiTa, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En diciembre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 33.050 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.2 Proporción diaria de viajes con peaje (%)][E3.2] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3] · [E3.5 Regla R10: cobros anómalos del peaje][E3.5]

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

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 24,80 % de la tarifa en 2025 frente a 24,93 % en 2024 (21,3 % y 22,2 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 8,4 % al 26,8 % de los viajes (289.128 → 1.084.771 con tarifa > 0) y cuya propina cae del 5,40 % al 2,01 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 9,7 % al 28,2 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 76,8 % al 62,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5] · [E4.6 Viajes y peso de cada forma de pago][E4.6] · [E4.4 Regla R05: viajes sin cantidad de pasajeros][E4.4]

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

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 4,5 % (335.512 → 320.421) mientras el total de la ciudad sube un 14,9 %, así que su peso cae del 9,5 % al 7,9 % de los viajes. Por aeropuerto, JFK cae −2,0 % y LaGuardia cae −7,5 %. La tarifa promedio se mantiene (US$ 56,92 → US$ 56,93), y la mediana baja de US$ 58,30 a US$ 57,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]

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

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Diciembre 2025 tuvo 4.049.994 viajes válidos contra 3.526.288 en diciembre 2024: +523.706 viajes (+14,85 %). La recaudación total (total_amount) crece un 23,0 %, de US$ 103,4 M a US$ 127,1 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario casi no influye: diciembre 2025 tuvo 5 miércoles, y diciembre 2024, 5 domingos (días flojos). Todos los días de la semana crecen (por día), entre +9 % y +23 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 10,65 % (de US$ 20,34 a US$ 22,50). La mediana pasa de US$ 14,20 a US$ 17,00 (+19,7 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de diciembre 2025 hay más viajes Flex Fare, que son más caros (US$ 27,36 contra US$ 20,72 del resto) y pasan del 8 % al 27 % de los viajes y menos viajes a aeropuertos (del 9,5 % al 7,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 2,7 % (de US$ 20,17 a US$ 20,72). El viaje promedio es más largo: 3,52 contra 3,32 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 3,87 % al 5,92 % de las filas leídas (255.012 filas en diciembre 2025 y 142.083 en diciembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,55 % contra 2,06 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,35 % contra 0,03 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en diciembre 2025 (+14,9 % de viajes, +23,0 % de recaudación). Las zonas que más suman viajes son East Village (+29,4 %), Kips Bay (+33,7 %) y East Harlem South (+56,6 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 72,1 % de los viajes de diciembre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +11,7 %, Greenwich Village South +12,7 % y West Village +12,0 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,52 contra 3,32 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 17,00). La propina con tarjeta no se mueve (24,9 % → 24,8 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 38 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 3.033,10, en 2024) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (diciembre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 5,92 % y del 3,87 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-12 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-12`](http://localhost:8090/superset/dashboard/respaldo-local-2025-12/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 311 números en este reporte, 311 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:04 UTC, corrida `20261124T025852Z-98bd98`).

- Tablero `respaldo-local-2025-12`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.790 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 311 de 311 se ven en los charts que cita su bloque.
<!-- VERIFICACION:END -->

| chart | qué sustenta | tabla | dónde se cita |
|---|---|---|---|
| [E0.1 Viajes válidos][E0.1] | viajes válidos del mes | `marts.ev_indicadores` | Resumen |
| [E0.2 Viajes, año anterior][E0.2] | viajes válidos del mes de comparación | `marts.ev_indicadores` | Resumen |
| [E0.3 Variación de viajes (%)][E0.3] | variación interanual de los viajes | `marts.ev_indicadores` | Resumen |
| [E0.4 Recaudación (USD)][E0.4] | recaudación total del mes | `marts.ev_indicadores` | Resumen |
| [E0.6 Recaudación, cambio (%)][E0.6] | variación interanual de la recaudación | `marts.ev_indicadores` | Resumen |
| [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] | filas leídas, aceptadas, en cuarentena y con advertencias de cada archivo | `marts.ev_calidad` | Calidad, Pregunta 6 |
| [EC.2 Filas que violan cada regla de calidad][EC.2] | filas y porcentaje por regla en los dos meses | `marts.ev_reglas` | Calidad, Pregunta 6 |
| [EC.4 Contrato de esquema: novedades de cada archivo][EC.4] | qué trajo cada parquet respecto del contrato y qué se hizo | `marts.ev_esquema` | Calidad |
| [E1.1 Top 10 de zonas de pickup del mes][E1.1] | respuesta de la pregunta 1 | `marts.ev_zonas` | Pregunta 1 |
| [E1.3 Top 10 del mismo mes del año anterior][E1.3] | quién encabezaba, quién entra y quién sale | `marts.ev_zonas` | Pregunta 1 |
| [E1.4 Concentración y composición del top 10][E1.4] | peso del top 10, zonas en Manhattan, zonas que crecen o caen y total de la ciudad | `marts.ev_indicadores` | Pregunta 1 |
| [E1.5 Pickups en JFK y LaGuardia][E1.5] | puesto y variación de los dos aeropuertos | `marts.ev_zonas` | Pregunta 1 |
| [E1.6 Pickups por borough][E1.6] | peso y variación de cada borough | `marts.ev_boroughs` | Pregunta 1 |
| [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1] | respuesta de la pregunta 2: volumen, ingreso por viaje y puesto de cada hora | `marts.ev_horas` | Pregunta 2 |
| [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5] | resumen de la pregunta 2 | `marts.ev_indicadores` | Pregunta 2 |
| [E2.6 Las 24 horas: viajes de aeropuerto y distancia media][E2.6] | por qué gana una hora: peso de los aeropuertos y distancia | `marts.ev_horas` | Pregunta 2 |
| [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7] | si un puesto del ranking lo infla un solo viaje | `marts.ev_horas` | Pregunta 2, Conclusiones |
| [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] | respuesta de la pregunta 3 (total del mes) y el efecto de la fecha de inicio | `marts.ev_indicadores` | Pregunta 3 |
| [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3] | respuesta de la pregunta 3 (zonas con 1.000 viajes o más) | `marts.ev_cbd_zonas` | Pregunta 3 |
| [E3.2 Proporción diaria de viajes con peaje (%)][E3.2] | cuándo empieza el cobro | `marts.ev_dias` | Pregunta 3 |
| [E3.5 Regla R10: cobros anómalos del peaje][E3.5] | filas marcadas por la regla R10 | `marts.ev_reglas` | Pregunta 3 |
| [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] | respuesta de la pregunta 4: propina media y ponderada | `marts.ev_pagos` | Pregunta 4 |
| [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5] | la base de la propina de la pregunta 4 | `marts.ev_pagos` | Pregunta 4 |
| [E4.6 Viajes y peso de cada forma de pago][E4.6] | cuánto pesa cada forma de pago en los viajes | `marts.ev_pagos` | Pregunta 4 |
| [E4.4 Regla R05: viajes sin cantidad de pasajeros][E4.4] | advertencias por passenger_count | `marts.ev_reglas` | Pregunta 4 |
| [E5.1 Viajes y tarifas de los aeropuertos][E5.1] | respuesta de la pregunta 5 | `marts.ev_indicadores` | Pregunta 5 |
| [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4] | los viajes atípicos, con su recorrido y forma de pago | `marts.ev_tarifas_altas` | Pregunta 5, Pregunta 6 |
| [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] | respuesta de la pregunta 6 | `marts.ev_indicadores` | Pregunta 6 |
| [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] | cuántas veces aparece cada día y sus viajes por día | `marts.ev_dias_semana` | Pregunta 6 |
| [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5] | qué cambió en la composición de los viajes | `marts.ev_indicadores` | Pregunta 6 |
| [C1.1 Demanda: viajes y recaudación][C1.1] | conclusión 1, crecimiento o caída | `marts.ev_indicadores` | Conclusiones |
| [C1.2 Las 10 zonas que más mueven el total][C1.2] | conclusión 1, zonas que más suman o pierden viajes | `marts.ev_zonas` | Conclusiones |
| [C1.3 Aeropuertos contra el total de la ciudad][C1.3] | conclusión 1, aeropuertos | `marts.ev_zonas` | Conclusiones |
| [C2.1 Alcance del peaje CBD en los dos meses][C2.1] | conclusión 2, alcance del peaje | `marts.ev_indicadores` | Conclusiones |
| [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2] | conclusión 2, demanda donde se cobra el peaje | `marts.ev_cbd_zonas` | Conclusiones |
| [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1] | conclusión 3, viaje promedio | `marts.ev_indicadores` | Conclusiones |
| [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] | conclusión 4, promedios con y sin atípicas | `marts.ev_indicadores` | Conclusiones |
| [C4.2 Los viajes con las tarifas más altas][C4.2] | conclusión 4, cuáles son | `marts.ev_tarifas_altas` | Conclusiones |
| [C5.1 Cuarentena y reconciliación][C5.1] | conclusión 5, calidad | `marts.ev_calidad` | Conclusiones |
| [C5.2 Cambios de formato de los archivos][C5.2] | conclusión 5, esquema | `marts.ev_esquema` | Conclusiones |

Charts de apoyo visual del mismo tablero (mismas tablas): [E0.5 Recaudación, año anterior][E0.5], [E0.7 Viajes por día del mes][E0.7], [E0.8 Recaudación por día del mes (USD)][E0.8], [EC.3 Porcentaje de las filas leídas que viola cada regla][EC.3], [E1.2 Viajes del top 10, los dos meses][E1.2], [E1.7 Variación de pickups por borough (%)][E1.7], [E1.8 Todas las zonas y su variación][E1.8], [E2.2 Ingreso promedio por viaje según la hora (USD)][E2.2], [E2.3 Viajes según la hora][E2.3], [E2.4 Viajes de aeropuerto según la hora (%)][E2.4], [E3.4 Las 15 zonas con mayor proporción de viajes con peaje (%)][E3.4], [E4.2 Participación de cada forma de pago (%)][E4.2], [E4.3 Propina media por forma de pago (% de la tarifa)][E4.3], [E5.2 Viajes que tocan cada aeropuerto][E5.2], [E5.3 Tarifa de los viajes de aeropuerto (USD)][E5.3], [E6.3 Viajes por día, según el día de la semana][E6.3], [E6.4 Variación de los viajes por día (%)][E6.4], [E6.6 Tarifa media, media sin atípicas y mediana (USD)][E6.6].

<details><summary>Cada cifra y el chart donde se ve</summary>

Cuando un número redondeado aparece en más de una celda se indica cuántas.

| sección | cifra | chart | columna y fila |
|---|---:|---|---|
| Resumen | 4.049.994 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +14,9 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.526.288 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 127,1 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +23,0 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.305.006 | EC.1 | `filas_archivo` · 2025-12 (y 1 más) |
| Calidad | 4.305.006 | EC.1 | `filas_archivo` · 2025-12 (y 1 más) |
| Calidad | 4.049.994 | EC.1 | `aceptadas` · 2025-12 |
| Calidad | 255.012 | EC.1 | `cuarentena` · 2025-12 |
| Calidad | 5,92 | EC.1 | `pct_cuarentena` · 2025-12 |
| Calidad | 1.107.479 | EC.1 | `con_advertencias` · 2025-12 |
| Calidad | 25,73 | EC.1 | `pct_advertencias` · 2025-12 |
| Calidad | 3.668.371 | EC.1 | `filas_archivo` · 2024-12 (y 1 más) |
| Calidad | 3.668.371 | EC.1 | `filas_archivo` · 2024-12 (y 1 más) |
| Calidad | 3.526.288 | EC.1 | `aceptadas` · 2024-12 |
| Calidad | 142.083 | EC.1 | `cuarentena` · 2024-12 |
| Calidad | 3,87 | EC.1 | `pct_cuarentena` · 2024-12 |
| Calidad | 330.384 | EC.1 | `con_advertencias` · 2024-12 |
| Calidad | 9,01 | EC.1 | `pct_advertencias` · 2024-12 |
| Calidad | 9 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 34 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 58.021 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,35 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.223 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +1,31 | EC.2 | `cambio_pp` · R02 |
| Calidad | 152.853 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,55 | EC.2 | `pct_mes` · R03 |
| Calidad | 75.579 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,06 | EC.2 | `pct_anterior` · R03 |
| Calidad | +1,49 | EC.2 | `cambio_pp` · R03 |
| Calidad | 48.869 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,14 | EC.2 | `pct_mes` · R04 |
| Calidad | 70.496 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,92 | EC.2 | `pct_anterior` · R04 |
| Calidad | −0,79 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.214.309 | EC.2 | `filas_mes` · R05 |
| Calidad | 28,21 | EC.2 | `pct_mes` · R05 |
| Calidad | 356.688 | EC.2 | `filas_anterior` · R05 |
| Calidad | 9,72 | EC.2 | `pct_anterior` · R05 |
| Calidad | +18,48 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 53.451 | EC.2 | `filas_mes` · R08 |
| Calidad | 1,24 | EC.2 | `pct_mes` · R08 |
| Calidad | 83.686 | EC.2 | `filas_anterior` · R08 |
| Calidad | 2,28 | EC.2 | `pct_anterior` · R08 |
| Calidad | −1,04 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.150 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.063 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 33.050 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,77 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | +0,77 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 3,87 | EC.1 | `pct_cuarentena` · 2024-12 |
| Calidad | 5,92 | EC.1 | `pct_cuarentena` · 2025-12 |
| Calidad | 255.012 | EC.1 | `cuarentena` · 2025-12 |
| Calidad | 142.083 | EC.1 | `cuarentena` · 2024-12 |
| Calidad | 3,55 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,06 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,35 | EC.2 | `pct_mes` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.107.479 | EC.1 | `con_advertencias` · 2025-12 |
| Calidad | 25,7 | EC.1 | `pct_advertencias` · 2025-12 |
| Calidad | 28,2 | EC.2 | `pct_mes` · R05 |
| Calidad | 9,7 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 185.995 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 178.797 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 7.198 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 4,03 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 167.419 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 159.600 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 7.819 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 4,90 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 154.076 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 154.573 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -497 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -0,32 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 152.146 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 151.263 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | 883 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | 0,58 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 128.426 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 126.949 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 1.477 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 1,16 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 126.735 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 122.871 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 3.864 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 3,14 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 124.797 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 123.888 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 909 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 0,73 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 115.045 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 118.559 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -3.514 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -2,96 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 107.236 | E1.1 | `viajes_mes` · Upper West Side South Manhattan |
| Pregunta 1 | 104.346 | E1.1 | `viajes_anterior` · Upper West Side South Manhattan |
| Pregunta 1 | 2.890 | E1.1 | `variacion` · Upper West Side South Manhattan |
| Pregunta 1 | 2,77 | E1.1 | `variacion_pct` · Upper West Side South Manhattan |
| Pregunta 1 | 106.524 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 96.830 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | 9.694 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | 10,01 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | +0,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 3 más) |
| Pregunta 1 | +10,0 | E1.1 | `puesto_mes` · Union Sq Manhattan (y 4 más) |
| Pregunta 1 | −3,0 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan (y 1 más) |
| Pregunta 1 | 185.995 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +4,0 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 7 más) |
| Pregunta 1 | 4 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 10 más) |
| Pregunta 1 | +0,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 3 más) |
| Pregunta 1 | −5,2 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | 33,8 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 38,4 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 10.250 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 37.334 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +14,9 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 5 más) |
| Pregunta 2 | 33.884 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 36,68 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 5 más) |
| Pregunta 2 | 20.665 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 40,15 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 14 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_anterior` · 7:00 (y 6 más) |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 14 más) |
| Pregunta 2 | 36,68 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 40,15 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 33.884 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 251.670 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 15,5 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 7,9 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto (y 1 más) |
| Pregunta 2 | 6,09 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,52 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 27,8 | E2.6 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 15,5 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 6,55 | E2.6 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 6,09 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 8,6 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 1 más) |
| Pregunta 3 | 4.049.994 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.918.819 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 72,07 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 33.313 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 33.228 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,74 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 56.945 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 56.774 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,70 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 84.522 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 84.205 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,62 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99.393 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 98.936 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,54 | E3.3 | `pct_con_peaje` · East Village Manhattan |
| Pregunta 3 | 44.885 | E3.3 | `viajes` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 44.675 | E3.3 | `viajes_con_peaje` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 99,53 | E3.3 | `pct_con_peaje` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 72,07 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.918.819 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 4.049.994 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 4 más) |
| Pregunta 3 | 33.050 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 1.084.771 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,01 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,75 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.545.696 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,80 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,25 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 372.921 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 11.304 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 33.959 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 289.128 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 5,40 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 5,67 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.708.226 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 24,93 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,17 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 462.843 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 11 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 15.055 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 42.308 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 24,80 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 24,93 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,3 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,2 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 91 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 8,4 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 26,8 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 289.128 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1.084.771 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 5,40 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,01 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 9,7 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 28,2 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 76,8 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 62,9 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 320.421 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,93 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 180.591 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 142.391 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 335.512 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,92 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 184.294 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 153.875 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 4,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 335.512 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 320.421 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 14,9 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,5 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 7,9 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −2,0 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −7,5 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 56,92 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 56,93 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 58,30 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 57,60 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 4.049.994 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.526.288 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 523.706 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 14,85 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 22,50 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 20,34 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 10,65 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 4.049.994 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.526.288 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +523.706 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +14,85 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 23,0 | E6.1 | `variacion_pct` · Recaudación total (total_amount) (y 1 más) |
| Pregunta 6 | 103,4 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 127,1 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 5 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 5 más) |
| Pregunta 6 | +9 | E6.2 | `variacion_por_dia_pct` · jueves |
| Pregunta 6 | +23 | E6.2 | `variacion_por_dia_pct` · domingo (y 3 más) |
| Pregunta 6 | 10,65 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 20,34 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 22,50 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 14,20 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 17,00 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +19,7 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 27,36 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,72 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 8 | E6.5 | `valor_mes` · Viajes de más de 10 millas (y 3 más) |
| Pregunta 6 | 27 | E6.5 | `valor_mes` · Participación de Flex Fare (y 2 más) |
| Pregunta 6 | 9,5 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,9 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 2,7 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 20,17 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 20,72 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 3,52 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,32 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 3,87 | EC.1 | `pct_cuarentena` · 2024-12 |
| Pregunta 6 | 5,92 | EC.1 | `pct_cuarentena` · 2025-12 |
| Pregunta 6 | 255.012 | EC.1 | `cuarentena` · 2025-12 |
| Pregunta 6 | 142.083 | EC.1 | `cuarentena` · 2024-12 |
| Pregunta 6 | 3,55 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,06 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,35 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Conclusiones | +14,9 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +23,0 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +29,4 | C1.2 | `variacion_pct` · East Village Manhattan |
| Conclusiones | +33,7 | C1.2 | `variacion_pct` · Kips Bay Manhattan |
| Conclusiones | +56,6 | C1.2 | `variacion_pct` · East Harlem South Manhattan |
| Conclusiones | 72,1 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +11,7 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan |
| Conclusiones | +12,7 | C2.2 | `variacion_viajes_pct` · Greenwich Village South Manhattan |
| Conclusiones | +12,0 | C2.2 | `variacion_viajes_pct` · West Village Manhattan |
| Conclusiones | 3,52 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,32 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,20 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 17,00 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 24,9 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 24,8 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 38 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 3.033,10 | C4.1 | `valor_anterior` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,92 | C5.1 | `pct_cuarentena` · 2025-12 |
| Conclusiones | 3,87 | C5.1 | `pct_cuarentena` · 2024-12 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-12/#CHART-C5-2
