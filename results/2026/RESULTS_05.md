# Resultados: mayo 2026 vs mayo 2025

> En mayo 2026 los taxis amarillos hicieron 3.912.688 viajes válidos, −8,7 % que en mayo 2025 (4.284.351), con una recaudación de US$ 119,5 M (−1,0 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-05 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-05.parquet` y `yellow_tripdata_2025-05.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-05`](http://localhost:8090/superset/dashboard/respaldo-local-2026-05/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=05/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-05 | `yellow_tripdata_2026-05.parquet` | 4.090.836 | 4.090.836 | 3.912.688 | 178.148 | 4,35 % | 894.718 (21,87 %) | sí |
| 2025-05 | `yellow_tripdata_2025-05.parquet` | 4.591.845 | 4.591.845 | 4.284.351 | 307.494 | 6,70 % | 1.095.990 (23,87 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-05 | 2025-05 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 14 (0,00 %) | 24 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 52.063 (1,27 %) | 64.272 (1,40 %) | −0,13 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 113.167 (2,77 %) | 141.491 (3,08 %) | −0,32 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.877 (0,36 %) | 112.544 (2,45 %) | −2,09 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 967.904 (23,66 %) | 1.220.143 (26,57 %) | −2,91 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 19.159 (0,47 %) | 329.913 (7,18 %) | −6,72 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.020 (0,02 %) | 1.268 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.689 (0,24 %) | 52.625 (1,15 %) | −0,91 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 6,70 % al 4,35 % de las filas leídas (178.148 filas en mayo 2026 y 307.494 en mayo 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,77 % contra 3,08 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,27 % contra 1,40 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −2,09 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 894.718 filas aceptadas de mayo 2026 (21,9 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 23,7 %, contra 26,6 % en mayo 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de mayo 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de mayo 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 190.900 | 196.106 | -5.206 | -2,65 |
| Manhattan | Upper East Side North | 168.504 | 172.121 | -3.617 | -2,10 |
| Manhattan | Midtown Center | 155.366 | 174.894 | -19.528 | -11,17 |
| Queens | JFK Airport | 142.825 | 176.723 | -33.898 | -19,18 |
| Manhattan | Lincoln Square East | 119.903 | 129.721 | -9.818 | -7,57 |
| Manhattan | Midtown East | 116.235 | 125.584 | -9.349 | -7,44 |
| Manhattan | Penn Station/Madison Sq West | 109.942 | 123.140 | -13.198 | -10,72 |
| Manhattan | Times Sq/Theatre District | 107.782 | 129.165 | -21.383 | -16,55 |
| Manhattan | Upper West Side South | 104.044 | 107.604 | -3.560 | -3,31 |
| Manhattan | East Village | 103.389 | 107.499 | -4.110 | -3,82 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan y las diez caen, entre −2,1 % (Upper East Side North) y −19,2 % (JFK Airport). Upper East Side South lidera con 190.900 viajes (−2,7 %). Respecto de mayo 2025 entran al top 10 Upper West Side South y East Village y salen LaGuardia Airport y Union Sq. En los aeropuertos, JFK (puesto 4 del top) cae −19,2 % y LaGuardia (fuera del top) cae −14,0 %: los aeropuertos van peor que el total de la ciudad (−8,7 %). La concentración casi no cambia: el top 10 reúne el 33,7 % de los pickups (34,1 % en 2025). Fuera de Manhattan, Queens cae −19,2 % en sus pickups (413.861 → 334.597), contra −8,7 % del total.

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
| 2026 | 5 | 5 | 35.166 | 36,74 |
| 2025 | 5 | 5 | 34.116 | 33,20 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,74 en 2026 y US$ 33,20 en 2025. Es una hora de poco volumen (35.166 viajes, contra 254.138 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 16,7 % de sus viajes toca JFK o LaGuardia (contra 7,9 % en todo el mes) y la distancia media es de 6,13 millas (contra 3,52). El ingreso por viaje de esa hora sube un 10,7 % aunque los viajes de aeropuerto son menos (del 18,3 % al 16,7 % de los viajes de las 5:00): lo explican las tarifas y recargos de 2026.

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
| ALL ZONES |  | 3.912.688 | 2.611.323 | 66,74 |
| Penn Station/Madison Sq West | Manhattan | 109.942 | 106.376 | 96,76 |
| Midtown East | Manhattan | 116.235 | 112.058 | 96,41 |
| Sutton Place/Turtle Bay North | Manhattan | 62.291 | 59.731 | 95,89 |
| Midtown North | Manhattan | 96.892 | 92.697 | 95,67 |
| Midtown Center | Manhattan | 155.366 | 147.176 | 94,73 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 66,74 % de los viajes de mayo 2026 pagó cbd_congestion_fee (2.611.323 de 3.912.688, siempre US$ 0,75). Las cinco zonas con mayor proporción (Penn Station/Madison Sq West, Midtown East, Sutton Place/Turtle Bay North, Midtown North y Midtown Center, entre 94,7 % y 96,8 %) están todas en Manhattan, dentro de la zona de peaje. En mayo 2025 lo pagaba el 73,22 % de los viajes: la proporción baja −6,5 pp. La regla R10 marcó 9.689 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 5 | 0 | Flex Fare | 877.870 | 2,07 | 1,91 |
| 2026 | 5 | 1 | Credit card | 2.661.076 | 24,54 | 21,08 |
| 2026 | 5 | 2 | Cash | 353.250 | 0,00 | 0,00 |
| 2026 | 5 | 3 | No charge | 7.061 | 0,01 | 0,01 |
| 2026 | 5 | 4 | Dispute | 11.556 | 0,00 | 0,00 |
| 2025 | 5 | 0 | Flex Fare | 877.068 | 1,70 | 1,85 |
| 2025 | 5 | 1 | Credit card | 2.764.975 | 25,36 | 22,20 |
| 2025 | 5 | 2 | Cash | 382.959 | 0,00 | 0,00 |
| 2025 | 5 | 3 | No charge | 15.145 | 0,11 | 0,15 |
| 2025 | 5 | 4 | Dispute | 51.172 | 0,05 | 0,05 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina baja: 24,54 % de la tarifa en 2026 frente a 25,36 % en 2025 (21,1 % y 22,2 % ponderada), y deja propina el 90 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 25,0 % al 22,5 % de los viajes (877.068 → 877.870 con tarifa > 0) y cuya propina sube del 1,70 % al 2,07 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 bajan del 26,6 % al 23,7 % de las filas leídas. La tarjeta gana peso entre las formas de pago: del 64,5 % al 68,0 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 5 | 307.572 | 56,13 | 170.961 | 139.164 |
| 2025 | 5 | 372.036 | 57,27 | 212.939 | 162.577 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 17,3 % (372.036 → 307.572) mientras el total de la ciudad baja un 8,7 %, así que su peso cae del 8,7 % al 7,9 % de los viajes. Por aeropuerto, JFK cae −19,7 % y LaGuardia cae −14,4 %. La tarifa promedio baja de US$ 57,27 a US$ 56,13 (−2,0 %), y la mediana baja de US$ 58,00 a US$ 55,50. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.912.688 | 4.284.351 | -371.663 | -8,67 | 21,46 | 19,29 | 11,26 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Mayo 2026 tuvo 3.912.688 viajes válidos contra 4.284.351 en mayo 2025: −371.663 viajes (−8,67 %). La recaudación total (total_amount) cae un 1,0 %, de US$ 120,7 M a US$ 119,5 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Parte de la caída es de calendario: mayo 2026 tuvo 5 domingos (días flojos), y mayo 2025, 5 jueves (días fuertes). Con el calendario de 2025 la variación sería −8,1 %. Todos los días de la semana caen (por día), entre −5 % y −12 %, así que la baja es general.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 11,26 % (de US$ 19,29 a US$ 21,46). La mediana pasa de US$ 14,20 a US$ 16,30 (+14,8 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de mayo 2026 hay menos viajes Flex Fare, que son más caros (US$ 25,56 contra US$ 20,27 del resto) y pasan del 25 % al 22 % de los viajes, menos viajes a aeropuertos (del 8,7 % al 7,9 %) y menos viajes de más de 10 millas (del 7,9 % al 7,7 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,17 a US$ 20,27).
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 6,70 % al 4,35 % de las filas leídas (178.148 filas en mayo 2026 y 307.494 en mayo 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,77 % contra 3,08 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,27 % contra 1,40 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en mayo 2026 (−8,7 % de viajes, −1,0 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−19,2 %), Times Sq/Theatre District (−16,6 %) y Midtown Center (−11,2 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 66,7 % de los viajes de mayo 2026, contra 73,2 % en mayo 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es igual de largo (3,52 contra 3,55 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 16,30). La propina con tarjeta baja (25,4 % → 24,5 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 52 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 1.755,80, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 4,35 % y del 6,70 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-05 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-05`](http://localhost:8090/superset/dashboard/respaldo-local-2026-05/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 314 números en este reporte, 314 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:07 UTC, corrida `20261124T030441Z-aada0b`).

- Tablero `respaldo-local-2026-05`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.798 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 314 de 314 se ven en los charts que cita su bloque.
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
| Resumen | 3.912.688 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −8,7 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 4.284.351 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 119,5 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | −1,0 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.090.836 | EC.1 | `filas_archivo` · 2026-05 (y 1 más) |
| Calidad | 4.090.836 | EC.1 | `filas_archivo` · 2026-05 (y 1 más) |
| Calidad | 3.912.688 | EC.1 | `aceptadas` · 2026-05 |
| Calidad | 178.148 | EC.1 | `cuarentena` · 2026-05 |
| Calidad | 4,35 | EC.1 | `pct_cuarentena` · 2026-05 |
| Calidad | 894.718 | EC.1 | `con_advertencias` · 2026-05 |
| Calidad | 21,87 | EC.1 | `pct_advertencias` · 2026-05 |
| Calidad | 4.591.845 | EC.1 | `filas_archivo` · 2025-05 (y 1 más) |
| Calidad | 4.591.845 | EC.1 | `filas_archivo` · 2025-05 (y 1 más) |
| Calidad | 4.284.351 | EC.1 | `aceptadas` · 2025-05 |
| Calidad | 307.494 | EC.1 | `cuarentena` · 2025-05 |
| Calidad | 6,70 | EC.1 | `pct_cuarentena` · 2025-05 |
| Calidad | 1.095.990 | EC.1 | `con_advertencias` · 2025-05 |
| Calidad | 23,87 | EC.1 | `pct_advertencias` · 2025-05 |
| Calidad | 14 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 24 | EC.2 | `filas_anterior` · R01 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 52.063 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,27 | EC.2 | `pct_mes` · R02 |
| Calidad | 64.272 | EC.2 | `filas_anterior` · R02 |
| Calidad | 1,40 | EC.2 | `pct_anterior` · R02 |
| Calidad | −0,13 | EC.2 | `cambio_pp` · R02 |
| Calidad | 113.167 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,77 | EC.2 | `pct_mes` · R03 |
| Calidad | 141.491 | EC.2 | `filas_anterior` · R03 |
| Calidad | 3,08 | EC.2 | `pct_anterior` · R03 |
| Calidad | −0,32 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.877 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,36 | EC.2 | `pct_mes` · R04 |
| Calidad | 112.544 | EC.2 | `filas_anterior` · R04 |
| Calidad | 2,45 | EC.2 | `pct_anterior` · R04 |
| Calidad | −2,09 | EC.2 | `cambio_pp` · R04 |
| Calidad | 967.904 | EC.2 | `filas_mes` · R05 |
| Calidad | 23,66 | EC.2 | `pct_mes` · R05 |
| Calidad | 1.220.143 | EC.2 | `filas_anterior` · R05 |
| Calidad | 26,57 | EC.2 | `pct_anterior` · R05 |
| Calidad | −2,91 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 19.159 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,47 | EC.2 | `pct_mes` · R08 |
| Calidad | 329.913 | EC.2 | `filas_anterior` · R08 |
| Calidad | 7,18 | EC.2 | `pct_anterior` · R08 |
| Calidad | −6,72 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.020 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,02 | EC.2 | `pct_mes` · R09 |
| Calidad | 1.268 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R09 |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 9.689 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,24 | EC.2 | `pct_mes` · R10 |
| Calidad | 52.625 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,15 | EC.2 | `pct_anterior` · R10 |
| Calidad | −0,91 | EC.2 | `cambio_pp` · R10 |
| Calidad | 6,70 | EC.1 | `pct_cuarentena` · 2025-05 |
| Calidad | 4,35 | EC.1 | `pct_cuarentena` · 2026-05 |
| Calidad | 178.148 | EC.1 | `cuarentena` · 2026-05 |
| Calidad | 307.494 | EC.1 | `cuarentena` · 2025-05 |
| Calidad | 2,77 | EC.2 | `pct_mes` · R03 |
| Calidad | 3,08 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,27 | EC.2 | `pct_mes` · R02 |
| Calidad | 1,40 | EC.2 | `pct_anterior` · R02 |
| Calidad | −2,09 | EC.2 | `cambio_pp` · R04 |
| Calidad | 894.718 | EC.1 | `con_advertencias` · 2026-05 |
| Calidad | 21,9 | EC.1 | `pct_advertencias` · 2026-05 |
| Calidad | 23,7 | EC.2 | `pct_mes` · R05 |
| Calidad | 26,6 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 190.900 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 196.106 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | -5.206 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | -2,65 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 168.504 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 172.121 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | -3.617 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | -2,10 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 155.366 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 174.894 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -19.528 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -11,17 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 142.825 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 176.723 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -33.898 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -19,18 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 119.903 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 129.721 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -9.818 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -7,57 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 116.235 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 125.584 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -9.349 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -7,44 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 109.942 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 123.140 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -13.198 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -10,72 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 107.782 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 129.165 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -21.383 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -16,55 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 104.044 | E1.1 | `viajes_mes` · Upper West Side South Manhattan |
| Pregunta 1 | 107.604 | E1.1 | `viajes_anterior` · Upper West Side South Manhattan |
| Pregunta 1 | -3.560 | E1.1 | `variacion` · Upper West Side South Manhattan |
| Pregunta 1 | -3,31 | E1.1 | `variacion_pct` · Upper West Side South Manhattan |
| Pregunta 1 | 103.389 | E1.1 | `viajes_mes` · East Village Manhattan |
| Pregunta 1 | 107.499 | E1.1 | `viajes_anterior` · East Village Manhattan |
| Pregunta 1 | -4.110 | E1.1 | `variacion` · East Village Manhattan |
| Pregunta 1 | -3,82 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | −2,1 | E1.1 | `variacion_pct` · Upper East Side North Manhattan (y 1 más) |
| Pregunta 1 | −19,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 3 más) |
| Pregunta 1 | 190.900 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | −2,7 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 4 | E1.1 | `puesto_anterior` · Upper East Side North Manhattan (y 7 más) |
| Pregunta 1 | −19,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 3 más) |
| Pregunta 1 | −14,0 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | −8,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 33,7 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 34,1 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | −19,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 3 más) |
| Pregunta 1 | 413.861 | E1.6 | `viajes_anterior` · Queens |
| Pregunta 1 | 334.597 | E1.6 | `viajes_mes` · Queens |
| Pregunta 1 | −8,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 4 más) |
| Pregunta 2 | 35.166 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 36,74 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 4 más) |
| Pregunta 2 | 34.116 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 33,20 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 13 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_anterior` · 10:00 (y 7 más) |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 13 más) |
| Pregunta 2 | 36,74 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 33,20 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 35.166 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 254.138 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 16,7 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 7,9 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 2 | 6,13 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,52 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 10,7 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 2 más) |
| Pregunta 2 | 18,3 | E2.6 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 16,7 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 3 | 3.912.688 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.611.323 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 66,74 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 109.942 | E3.3 | `viajes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 106.376 | E3.3 | `viajes_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 96,76 | E3.3 | `pct_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 116.235 | E3.3 | `viajes` · Midtown East Manhattan |
| Pregunta 3 | 112.058 | E3.3 | `viajes_con_peaje` · Midtown East Manhattan |
| Pregunta 3 | 96,41 | E3.3 | `pct_con_peaje` · Midtown East Manhattan |
| Pregunta 3 | 62.291 | E3.3 | `viajes` · Sutton Place/Turtle Bay North Manhattan |
| Pregunta 3 | 59.731 | E3.3 | `viajes_con_peaje` · Sutton Place/Turtle Bay North Manhattan |
| Pregunta 3 | 95,89 | E3.3 | `pct_con_peaje` · Sutton Place/Turtle Bay North Manhattan |
| Pregunta 3 | 96.892 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 92.697 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 95,67 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 155.366 | E3.3 | `viajes` · Midtown Center Manhattan |
| Pregunta 3 | 147.176 | E3.3 | `viajes_con_peaje` · Midtown Center Manhattan |
| Pregunta 3 | 94,73 | E3.3 | `pct_con_peaje` · Midtown Center Manhattan |
| Pregunta 3 | 66,74 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.611.323 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.912.688 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 94,7 | E3.3 | `pct_con_peaje` · Midtown Center Manhattan |
| Pregunta 3 | 96,8 | E3.3 | `pct_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 73,22 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | −6,5 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.689 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 877.870 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,07 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,91 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.661.076 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,54 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,08 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 353.250 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 7.061 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 3 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 3 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 11.556 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 877.068 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,70 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,85 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.764.975 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,36 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,20 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 382.959 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 15.145 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,11 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,15 | E4.1 | `propina_ponderada_pct_anterior` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 51.172 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute (y 1 más) |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute (y 1 más) |
| Pregunta 4 | 24,54 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,36 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,1 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,2 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 90 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 25,0 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 22,5 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 877.068 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 877.870 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,70 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,07 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 26,6 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 23,7 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 64,5 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 68,0 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 307.572 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,13 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 170.961 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 139.164 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 372.036 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,27 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 212.939 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 162.577 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 17,3 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 372.036 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 307.572 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 8,7 | E5.1 | `variacion_pct` · Viajes válidos (y 1 más) |
| Pregunta 5 | 8,7 | E5.1 | `variacion_pct` · Viajes válidos (y 1 más) |
| Pregunta 5 | 7,9 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −19,7 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −14,4 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 57,27 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 56,13 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −2,0 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 58,00 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 55,50 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.912.688 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 4.284.351 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -371.663 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -8,67 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 21,46 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,29 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 11,26 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 3.912.688 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 4.284.351 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −371.663 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −8,67 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 1,0 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 120,7 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 119,5 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `variacion_por_dia_pct` · martes (y 6 más) |
| Pregunta 6 | 5 | E6.2 | `variacion_por_dia_pct` · martes (y 6 más) |
| Pregunta 6 | −8,1 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | −5 | E6.2 | `variacion_por_dia_pct` · martes |
| Pregunta 6 | −12 | E6.2 | `variacion_por_dia_pct` · domingo |
| Pregunta 6 | 11,26 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,29 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 21,46 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 14,20 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 16,30 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +14,8 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 25,56 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,27 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 25 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 22 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 8,7 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,9 | E6.5 | `valor_anterior` · Viajes de más de 10 millas (y 1 más) |
| Pregunta 6 | 7,9 | E6.5 | `valor_anterior` · Viajes de más de 10 millas (y 1 más) |
| Pregunta 6 | 7,7 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 20,17 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 20,27 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 6,70 | EC.1 | `pct_cuarentena` · 2025-05 |
| Pregunta 6 | 4,35 | EC.1 | `pct_cuarentena` · 2026-05 |
| Pregunta 6 | 178.148 | EC.1 | `cuarentena` · 2026-05 |
| Pregunta 6 | 307.494 | EC.1 | `cuarentena` · 2025-05 |
| Pregunta 6 | 2,77 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 3,08 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,27 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 1,40 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −8,7 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | −1,0 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −19,2 | C1.2 | `variacion_pct` · JFK Airport Queens (y 1 más) |
| Conclusiones | −16,6 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | −11,2 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | 66,7 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 73,2 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,52 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,55 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,20 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 16,30 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,4 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 24,5 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 52 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 1.755,80 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,35 | C5.1 | `pct_cuarentena` · 2026-05 |
| Conclusiones | 6,70 | C5.1 | `pct_cuarentena` · 2025-05 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-05/#CHART-C5-2
