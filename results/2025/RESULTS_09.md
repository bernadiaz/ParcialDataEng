# Resultados: septiembre 2025 vs septiembre 2024

> En septiembre 2025 los taxis amarillos hicieron 3.996.265 viajes válidos, +14,2 % que en septiembre 2024 (3.498.989), con una recaudación de US$ 115,2 M (+12,1 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-09 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-09.parquet` y `yellow_tripdata_2024-09.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-09`](http://localhost:8090/superset/dashboard/respaldo-local-2025-09/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T015201Z-299545`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=09/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-09 | `yellow_tripdata_2025-09.parquet` | 4.251.015 | 4.251.015 | 3.996.265 | 254.750 | 5,99 % | 1.010.489 (23,77 %) | sí |
| 2024-09 | `yellow_tripdata_2024-09.parquet` | 3.633.030 | 3.633.030 | 3.498.989 | 134.041 | 3,69 % | 478.197 (13,16 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-09 | 2024-09 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 49 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 57.179 (1,35 %) | 1.161 (0,03 %) | +1,31 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 124.697 (2,93 %) | 81.288 (2,24 %) | +0,70 pp |
| R04 | reject | Total cobrado faltante o negativo. | 78.492 (1,85 %) | 56.109 (1,54 %) | +0,30 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.089.381 (25,63 %) | 514.077 (14,15 %) | +11,48 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 257.250 (6,05 %) | 77.288 (2,13 %) | +3,92 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.216 (0,03 %) | 1.199 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 52.097 (1,23 %) | 0 (0,00 %) | +1,23 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 3,69 % al 5,99 % de las filas leídas (254.750 filas en septiembre 2025 y 134.041 en septiembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,93 % contra 2,24 %) y R04 (total cobrado faltante o negativo: 1,85 % contra 1,54 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,31 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 1.010.489 filas aceptadas de septiembre 2025 (23,8 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 25,6 %, contra 14,2 % en septiembre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de septiembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de septiembre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 178.552 | 162.003 | 16.549 | 10,22 |
| Queens | JFK Airport | 169.419 | 176.441 | -7.022 | -3,98 |
| Manhattan | Midtown Center | 159.404 | 149.535 | 9.869 | 6,60 |
| Manhattan | Upper East Side North | 154.352 | 145.676 | 8.676 | 5,96 |
| Manhattan | Penn Station/Madison Sq West | 129.298 | 116.953 | 12.345 | 10,56 |
| Manhattan | Midtown East | 122.012 | 114.097 | 7.915 | 6,94 |
| Manhattan | Times Sq/Theatre District | 114.854 | 109.245 | 5.609 | 5,13 |
| Manhattan | Union Sq | 107.000 | 97.561 | 9.439 | 9,67 |
| Manhattan | East Chelsea | 106.711 | 101.167 | 5.544 | 5,48 |
| Manhattan | Murray Hill | 106.497 | 98.526 | 7.971 | 8,09 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +5,1 % en Times Sq/Theatre District y +10,6 % en Penn Station/Madison Sq West) y una cae (JFK Airport −4,0 %). Upper East Side South lidera con 178.552 viajes (+10,2 %) y desplaza a JFK Airport, que encabezaba septiembre 2024. Respecto de septiembre 2024 entran al top 10 Union Sq y Murray Hill y salen LaGuardia Airport y Lincoln Square East. En los aeropuertos, JFK (puesto 2 del top) cae −4,0 % y LaGuardia (fuera del top) cae −2,9 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 33,7 % de los pickups, frente al 36,8 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (10.842 → 29.050), aunque sobre una base chica, contra +14,2 % del total.

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
| 2025 | 9 | 16 | 222.524 | 33,99 |
| 2024 | 9 | 5 | 21.797 | 36,91 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 16:00 en 2025 (US$ 33,99) y las 5:00 en 2024 (US$ 36,91). Además es una hora de mucho movimiento (222.524 viajes; la hora pico es las 18:00 con 260.300). Gana porque a esa hora pesan los viajes largos: el 11,3 % de sus viajes toca JFK o LaGuardia (contra 8,4 % en todo el mes).

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1] · [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5]

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
| ALL ZONES |  | 3.996.265 | 2.957.534 | 74,01 |
| SoHo | Manhattan | 36.110 | 36.038 | 99,80 |
| Greenwich Village South | Manhattan | 58.581 | 58.456 | 99,79 |
| West Village | Manhattan | 88.340 | 88.098 | 99,73 |
| Greenwich Village North | Manhattan | 55.884 | 55.708 | 99,69 |
| Midtown North | Manhattan | 94.344 | 94.023 | 99,66 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 74,01 % de los viajes de septiembre 2025 pagó cbd_congestion_fee (2.957.534 de 3.996.265, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Greenwich Village North y Midtown North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En septiembre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 52.097 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 9 | 0 | Flex Fare | 827.190 | 1,44 | 1,49 |
| 2025 | 9 | 1 | Credit card | 2.605.862 | 25,82 | 21,39 |
| 2025 | 9 | 2 | Cash | 338.108 | 0,00 | 0,00 |
| 2025 | 9 | 3 | No charge | 14.000 | 0,08 | 0,03 |
| 2025 | 9 | 4 | Dispute | 52.082 | 0,05 | 0,04 |
| 2024 | 9 | 0 | Flex Fare | 430.353 | 2,43 | 2,66 |
| 2024 | 9 | 1 | Credit card | 2.580.440 | 24,37 | 21,72 |
| 2024 | 9 | 2 | Cash | 422.242 | 0,00 | 0,00 |
| 2024 | 9 | 3 | No charge | 13.409 | 0,11 | 0,04 |
| 2024 | 9 | 4 | Dispute | 36.027 | 0,08 | 0,06 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina sube: 25,82 % de la tarifa en 2025 frente a 24,37 % en 2024 (21,4 % y 21,7 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 12,8 % al 24,7 % de los viajes (430.353 → 827.190 con tarifa > 0) y cuya propina cae del 2,43 % al 1,44 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 14,2 % al 25,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 73,7 % al 65,2 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.4 Regla R05: viajes sin cantidad de pasajeros][E4.4]

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
| 2025 | 9 | 336.219 | 58,25 | 197.728 | 141.541 |
| 2024 | 9 | 353.323 | 57,52 | 208.645 | 147.694 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 4,8 % (353.323 → 336.219) mientras el total de la ciudad sube un 14,2 %, así que su peso cae del 10,1 % al 8,4 % de los viajes. Por aeropuerto, JFK cae −5,2 % y LaGuardia cae −4,2 %. La tarifa promedio sube de US$ 57,52 a US$ 58,25 (+1,3 %), pero esa suba no es real: la produce un solo viaje de 2025 con fare_amount = US$ 323.800,27 (de JFK Airport a Midtown South, 11,8 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 57,50 a US$ 57,26 (−0,4 %), y la mediana baja de US$ 60,40 a US$ 58,30. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.996.265 | 3.498.989 | 497.276 | 14,21 | 19,99 | 20,54 | -2,70 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Septiembre 2025 tuvo 3.996.265 viajes válidos contra 3.498.989 en septiembre 2024: +497.276 viajes (+14,21 %). La recaudación total (total_amount) crece un 12,1 %, de US$ 102,7 M a US$ 115,2 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario casi no influye: septiembre 2025 tuvo 5 martes (días flojos), y septiembre 2024, 5 domingos (días flojos). Todos los días de la semana crecen (por día), entre +9 % y +23 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 2,70 % (de US$ 20,54 a US$ 19,99); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 323.800) la baja es del 3,1 % (de US$ 20,54 a US$ 19,90). La mediana pasa de US$ 14,76 a US$ 14,90 (+0,9 %).
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de septiembre 2025 hay más viajes Flex Fare, que son más baratos (US$ 17,64 contra US$ 20,65 del resto) y pasan del 13 % al 25 % de los viajes, menos viajes a aeropuertos (del 10,1 % al 8,4 %) y menos viajes de más de 10 millas (del 8,6 % al 8,3 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,70 a US$ 20,65). El viaje promedio es más largo: 3,63 contra 3,53 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 3,69 % al 5,99 % de las filas leídas (254.750 filas en septiembre 2025 y 134.041 en septiembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,93 % contra 2,24 %) y R04 (total cobrado faltante o negativo: 1,85 % contra 1,54 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en septiembre 2025 (+14,2 % de viajes, +12,1 % de recaudación). Las zonas que más suman viajes son East Village (+24,0 %), Upper East Side South (+10,2 %) y West Chelsea/Hudson Yards (+22,5 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 74,0 % de los viajes de septiembre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +11,4 %, Greenwich Village South +9,1 % y West Village +4,4 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,63 contra 3,53 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,76 → US$ 14,90). La propina con tarjeta sube (24,4 % → 25,8 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Los promedios son frágiles: 51 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 323.800,27, en 2025) alcanzan para mover la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (septiembre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 5,99 % y del 3,69 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-09 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-09`](http://localhost:8090/superset/dashboard/respaldo-local-2025-09/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 316 números en este reporte, 316 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:20 UTC, corrida `20261124T021601Z-5b0c2e`).

- Tablero `respaldo-local-2025-09`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.648 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 316 de 316 se ven en los charts que cita su bloque.
<!-- VERIFICACION:END -->

| chart | qué sustenta | tabla | dónde se cita |
|---|---|---|---|
| [E0.1 Viajes válidos del mes][E0.1] | viajes válidos del mes | `marts.ev_indicadores` | Resumen |
| [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] | viajes válidos del mes de comparación | `marts.ev_indicadores` | Resumen |
| [E0.3 Variación de viajes (%)][E0.3] | variación interanual de los viajes | `marts.ev_indicadores` | Resumen |
| [E0.4 Recaudación del mes (USD)][E0.4] | recaudación total del mes | `marts.ev_indicadores` | Resumen |
| [E0.6 Variación de la recaudación (%)][E0.6] | variación interanual de la recaudación | `marts.ev_indicadores` | Resumen |
| [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] | filas leídas, aceptadas, en cuarentena y con advertencias de cada archivo | `marts.ev_calidad` | Calidad, Pregunta 6 |
| [EC.2 Filas que violan cada regla de calidad][EC.2] | filas y porcentaje por regla en los dos meses | `marts.ev_reglas` | Calidad, Pregunta 6 |
| [EC.4 Contrato de esquema: novedades de cada archivo][EC.4] | qué trajo cada parquet respecto del contrato y qué se hizo | `marts.ev_esquema` | Calidad |
| [E1.1 Top 10 de zonas de pickup del mes][E1.1] | respuesta de la pregunta 1 | `marts.ev_zonas` | Pregunta 1 |
| [E1.3 Top 10 del mismo mes del año anterior][E1.3] | quién encabezaba, quién entra y quién sale | `marts.ev_zonas` | Pregunta 1 |
| [E1.4 Concentración y composición del top 10][E1.4] | peso del top 10, zonas en Manhattan, zonas que crecen o caen y total de la ciudad | `marts.ev_indicadores` | Pregunta 1 |
| [E1.5 Pickups en JFK y LaGuardia][E1.5] | puesto y variación de los dos aeropuertos | `marts.ev_zonas` | Pregunta 1 |
| [E1.6 Pickups por borough][E1.6] | peso y variación de cada borough | `marts.ev_boroughs` | Pregunta 1 |
| [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1] | respuesta de la pregunta 2 y sus causas, hora por hora | `marts.ev_horas` | Pregunta 2, Conclusiones |
| [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5] | resumen de la pregunta 2 | `marts.ev_indicadores` | Pregunta 2 |
| [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] | respuesta de la pregunta 3 (total del mes) y el efecto de la fecha de inicio | `marts.ev_indicadores` | Pregunta 3 |
| [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3] | respuesta de la pregunta 3 (zonas con 1.000 viajes o más) | `marts.ev_cbd_zonas` | Pregunta 3 |
| [E3.2 Proporción diaria de viajes con peaje (%)][E3.2] | cuándo empieza el cobro | `marts.ev_dias` | Pregunta 3 |
| [E3.5 Regla R10: cobros anómalos del peaje][E3.5] | filas marcadas por la regla R10 | `marts.ev_reglas` | Pregunta 3 |
| [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] | respuesta de la pregunta 4 y peso de cada forma de pago | `marts.ev_pagos` | Pregunta 4 |
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

Charts de apoyo visual del mismo tablero (mismas tablas): [E0.5 Recaudación, mismo mes del año anterior (USD)][E0.5], [E0.7 Viajes por día del mes][E0.7], [E0.8 Recaudación por día del mes (USD)][E0.8], [EC.3 Porcentaje de las filas leídas que viola cada regla][EC.3], [E1.2 Viajes del top 10, los dos meses][E1.2], [E1.7 Variación de pickups por borough (%)][E1.7], [E1.8 Todas las zonas y su variación][E1.8], [E2.2 Ingreso promedio por viaje según la hora (USD)][E2.2], [E2.3 Viajes según la hora][E2.3], [E2.4 Viajes de aeropuerto según la hora (%)][E2.4], [E3.4 Las 15 zonas con mayor proporción de viajes con peaje (%)][E3.4], [E4.2 Participación de cada forma de pago (%)][E4.2], [E4.3 Propina media por forma de pago (% de la tarifa)][E4.3], [E5.2 Viajes que tocan cada aeropuerto][E5.2], [E5.3 Tarifa de los viajes de aeropuerto (USD)][E5.3], [E6.3 Viajes por día, según el día de la semana][E6.3], [E6.4 Variación de los viajes por día (%)][E6.4], [E6.6 Tarifa media, media sin atípicas y mediana (USD)][E6.6].

<details><summary>Cada cifra y el chart donde se ve</summary>

Cuando un número redondeado aparece en más de una celda se indica cuántas.

| sección | cifra | chart | columna y fila |
|---|---:|---|---|
| Resumen | 3.996.265 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +14,2 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.498.989 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 115,2 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +12,1 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.251.015 | EC.1 | `filas_archivo` · 2025-09 (y 1 más) |
| Calidad | 4.251.015 | EC.1 | `filas_archivo` · 2025-09 (y 1 más) |
| Calidad | 3.996.265 | EC.1 | `aceptadas` · 2025-09 |
| Calidad | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Calidad | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Calidad | 1.010.489 | EC.1 | `con_advertencias` · 2025-09 |
| Calidad | 23,77 | EC.1 | `pct_advertencias` · 2025-09 |
| Calidad | 3.633.030 | EC.1 | `filas_archivo` · 2024-09 (y 1 más) |
| Calidad | 3.633.030 | EC.1 | `filas_archivo` · 2024-09 (y 1 más) |
| Calidad | 3.498.989 | EC.1 | `aceptadas` · 2024-09 |
| Calidad | 134.041 | EC.1 | `cuarentena` · 2024-09 |
| Calidad | 3,69 | EC.1 | `pct_cuarentena` · 2024-09 |
| Calidad | 478.197 | EC.1 | `con_advertencias` · 2024-09 |
| Calidad | 13,16 | EC.1 | `pct_advertencias` · 2024-09 |
| Calidad | 7 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 49 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 57.179 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,35 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.161 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +1,31 | EC.2 | `cambio_pp` · R02 |
| Calidad | 124.697 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,93 | EC.2 | `pct_mes` · R03 |
| Calidad | 81.288 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,24 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,70 | EC.2 | `cambio_pp` · R03 |
| Calidad | 78.492 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,85 | EC.2 | `pct_mes` · R04 |
| Calidad | 56.109 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,54 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,30 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.089.381 | EC.2 | `filas_mes` · R05 |
| Calidad | 25,63 | EC.2 | `pct_mes` · R05 |
| Calidad | 514.077 | EC.2 | `filas_anterior` · R05 |
| Calidad | 14,15 | EC.2 | `pct_anterior` · R05 |
| Calidad | +11,48 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 257.250 | EC.2 | `filas_mes` · R08 |
| Calidad | 6,05 | EC.2 | `pct_mes` · R08 |
| Calidad | 77.288 | EC.2 | `filas_anterior` · R08 |
| Calidad | 2,13 | EC.2 | `pct_anterior` · R08 |
| Calidad | +3,92 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.216 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.199 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 52.097 | EC.2 | `filas_mes` · R10 |
| Calidad | 1,23 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | +1,23 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 3,69 | EC.1 | `pct_cuarentena` · 2024-09 |
| Calidad | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Calidad | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Calidad | 134.041 | EC.1 | `cuarentena` · 2024-09 |
| Calidad | 2,93 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,24 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,85 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,54 | EC.2 | `pct_anterior` · R04 |
| Calidad | +1,31 | EC.2 | `cambio_pp` · R02 |
| Calidad | 1.010.489 | EC.1 | `con_advertencias` · 2025-09 |
| Calidad | 23,8 | EC.1 | `pct_advertencias` · 2025-09 |
| Calidad | 25,6 | EC.2 | `pct_mes` · R05 |
| Calidad | 14,2 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 178.552 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 162.003 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 16.549 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 10,22 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 169.419 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 176.441 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -7.022 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -3,98 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 159.404 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 149.535 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 9.869 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 6,60 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 154.352 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 145.676 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 8.676 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 5,96 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 129.298 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 116.953 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 12.345 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 10,56 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 122.012 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 114.097 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 7.915 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 6,94 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 114.854 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 109.245 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 5.609 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 5,13 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 107.000 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 97.561 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | 9.439 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | 9,67 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | 106.711 | E1.1 | `viajes_mes` · East Chelsea Manhattan |
| Pregunta 1 | 101.167 | E1.1 | `viajes_anterior` · East Chelsea Manhattan |
| Pregunta 1 | 5.544 | E1.1 | `variacion` · East Chelsea Manhattan |
| Pregunta 1 | 5,48 | E1.1 | `variacion_pct` · East Chelsea Manhattan |
| Pregunta 1 | 106.497 | E1.1 | `viajes_mes` · Murray Hill Manhattan |
| Pregunta 1 | 98.526 | E1.1 | `viajes_anterior` · Murray Hill Manhattan |
| Pregunta 1 | 7.971 | E1.1 | `variacion` · Murray Hill Manhattan |
| Pregunta 1 | 8,09 | E1.1 | `variacion_pct` · Murray Hill Manhattan |
| Pregunta 1 | +5,1 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan (y 1 más) |
| Pregunta 1 | +10,6 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan (y 1 más) |
| Pregunta 1 | −4,0 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 178.552 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +10,2 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 2 | E1.1 | `puesto_anterior` · Upper East Side South Manhattan (y 8 más) |
| Pregunta 1 | −4,0 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −2,9 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | 33,7 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 36,8 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 10.842 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 29.050 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +14,2 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 16 | E2.1 | `pct_aeropuerto_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 222.524 | E2.1 | `viajes_mes` · 16:00 |
| Pregunta 2 | 33,99 | E2.1 | `ingreso_viaje_mes` · 16:00 |
| Pregunta 2 | 5 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 8 más) |
| Pregunta 2 | 21.797 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 36,91 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 16:00 | E2.1 | `pct_aeropuerto_mes` · 5:00 (y 4 más) |
| Pregunta 2 | 5:00 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 9 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 10:00 (y 4 más) |
| Pregunta 2 | 33,99 | E2.1 | `ingreso_viaje_mes` · 16:00 (y 1 más) |
| Pregunta 2 | 36,91 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 2 más) |
| Pregunta 2 | 222.524 | E2.1 | `viajes_mes` · 16:00 (y 1 más) |
| Pregunta 2 | 260.300 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 11,3 | E2.1 | `pct_aeropuerto_mes` · 14:00 (y 2 más) |
| Pregunta 2 | 8,4 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 3 | 3.996.265 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.957.534 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 74,01 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 36.110 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 36.038 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,80 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 58.581 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 58.456 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,79 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 88.340 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 88.098 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,73 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 55.884 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 55.708 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,69 | E3.3 | `pct_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 94.344 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 94.023 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 99,66 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 74,01 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.957.534 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.996.265 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 4 más) |
| Pregunta 3 | 52.097 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 827.190 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,44 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,49 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 4 más) |
| Pregunta 4 | 2.605.862 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 25,82 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,39 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 338.108 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 14.000 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_mes` · No charge (y 1 más) |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_mes` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 52.082 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_mes` · Dispute |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 430.353 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 2,43 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,66 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 4 más) |
| Pregunta 4 | 2.580.440 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 24,37 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,72 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 422.242 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 13.409 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,11 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 36.027 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_mes` · No charge (y 1 más) |
| Pregunta 4 | 0,06 | E4.1 | `pct_con_propina_mes` · No charge (y 1 más) |
| Pregunta 4 | 25,82 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 24,37 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,4 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 21,7 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 92 | E4.1 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 12,8 | E4.1 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 24,7 | E4.1 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 430.353 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 827.190 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,43 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,44 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 14,2 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 25,6 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 73,7 | E4.1 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 65,2 | E4.1 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 336.219 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 58,25 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 197.728 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 141.541 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 353.323 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,52 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 208.645 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 147.694 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 4,8 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 353.323 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 336.219 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 14,2 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 10,1 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,4 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −5,2 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −4,2 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 57,52 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 58,25 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | +1,3 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 323.800,27 | E5.1 | `valor_mes` · Tarifa máxima de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 11,8 | E5.4 | `distancia_millas` · 2025-09 Cash puesto 1 |
| Pregunta 5 | 57,50 | E5.1 | `valor_anterior` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 57,26 | E5.1 | `valor_mes` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | −0,4 | E5.1 | `variacion_pct` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 60,40 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 58,30 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.996.265 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.498.989 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 497.276 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 14,21 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 19,99 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 20,54 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | -2,70 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.996.265 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.498.989 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +497.276 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +14,21 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 12,1 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 102,7 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 115,2 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | +9 | E6.2 | `variacion_por_dia_pct` · martes (y 1 más) |
| Pregunta 6 | +23 | E6.2 | `variacion_por_dia_pct` · domingo |
| Pregunta 6 | 2,70 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 20,54 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,99 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 323.800 | E6.1 | `valor_mes` · Tarifa máxima (y 1 más) |
| Pregunta 6 | 3,1 | E6.1 | `variacion_pct` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 20,54 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,90 | E6.1 | `valor_mes` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 14,76 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 14,90 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +0,9 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 17,64 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,65 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 13 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 25 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 10,1 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,4 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,6 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 8,3 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 20,70 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 20,65 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,63 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,53 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 3,69 | EC.1 | `pct_cuarentena` · 2024-09 |
| Pregunta 6 | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Pregunta 6 | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Pregunta 6 | 134.041 | EC.1 | `cuarentena` · 2024-09 |
| Pregunta 6 | 2,93 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,24 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,85 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,54 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +14,2 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +12,1 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +24,0 | C1.2 | `variacion_pct` · East Village Manhattan |
| Conclusiones | +10,2 | C1.2 | `variacion_pct` · Upper East Side South Manhattan |
| Conclusiones | +22,5 | C1.2 | `variacion_pct` · West Chelsea/Hudson Yards Manhattan |
| Conclusiones | 74,0 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +11,4 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan (y 1 más) |
| Conclusiones | +9,1 | C2.2 | `variacion_viajes_pct` · Greenwich Village South Manhattan |
| Conclusiones | +4,4 | C2.2 | `variacion_viajes_pct` · West Village Manhattan |
| Conclusiones | 3,63 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,53 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,76 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 14,90 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 24,4 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 25,8 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 51 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 323.800,27 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,99 | C5.1 | `pct_cuarentena` · 2025-09 |
| Conclusiones | 3,69 | C5.1 | `pct_cuarentena` · 2024-09 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-09/#CHART-C5-2
