# Resultados: septiembre 2026 vs septiembre 2025

> En septiembre 2026 los taxis amarillos hicieron 3.667.332 viajes válidos, −8,2 % que en septiembre 2025 (3.996.265), con una recaudación de US$ 118,0 M (+2,4 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-09 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-09.parquet` y `yellow_tripdata_2025-09.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-09`](http://localhost:8090/superset/dashboard/respaldo-local-2026-09/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=09/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09 | `yellow_tripdata_2026-09.parquet` | 3.876.044 | 3.876.044 | 3.667.332 | 208.712 | 5,38 % | 1.093.003 (28,20 %) | sí |
| 2025-09 | `yellow_tripdata_2025-09.parquet` | 4.251.015 | 4.251.015 | 3.996.265 | 254.750 | 5,99 % | 1.010.489 (23,77 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-09 | 2025-09 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 22 (0,00 %) | 7 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 48.202 (1,24 %) | 57.179 (1,35 %) | −0,10 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 147.283 (3,80 %) | 124.697 (2,93 %) | +0,87 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.688 (0,38 %) | 78.492 (1,85 %) | −1,47 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.200.950 (30,98 %) | 1.089.381 (25,63 %) | +5,36 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 18.461 (0,48 %) | 257.250 (6,05 %) | −5,58 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.168 (0,03 %) | 1.216 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.618 (0,25 %) | 52.097 (1,23 %) | −0,98 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 5,99 % al 5,38 % de las filas leídas (208.712 filas en septiembre 2026 y 254.750 en septiembre 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,80 % contra 2,93 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,24 % contra 1,35 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,47 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 1.093.003 filas aceptadas de septiembre 2026 (28,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 31,0 %, contra 25,6 % en septiembre 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de septiembre 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de septiembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 165.197 | 178.552 | -13.355 | -7,48 |
| Manhattan | Upper East Side North | 147.307 | 154.352 | -7.045 | -4,56 |
| Queens | JFK Airport | 146.023 | 169.419 | -23.396 | -13,81 |
| Manhattan | Midtown Center | 138.647 | 159.404 | -20.757 | -13,02 |
| Manhattan | Penn Station/Madison Sq West | 114.740 | 129.298 | -14.558 | -11,26 |
| Manhattan | Lincoln Square East | 106.139 | 105.757 | 382 | 0,36 |
| Manhattan | Midtown East | 106.049 | 122.012 | -15.963 | -13,08 |
| Manhattan | East Chelsea | 100.405 | 106.711 | -6.306 | -5,91 |
| Manhattan | Times Sq/Theatre District | 99.520 | 114.854 | -15.334 | -13,35 |
| Manhattan | East Village | 99.207 | 102.998 | -3.791 | -3,68 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve caen (entre −3,7 % en East Village y −13,8 % en JFK Airport) y una se mantiene. Upper East Side South lidera con 165.197 viajes (−7,5 %). Respecto de septiembre 2025 entran al top 10 Lincoln Square East y East Village y salen Union Sq y Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −13,8 % y LaGuardia (fuera del top) cae −7,2 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−8,2 %). La concentración casi no cambia: el top 10 reúne el 33,4 % de los pickups (33,7 % en 2025). Fuera de Manhattan, el Bronx cae −36,6 % en sus pickups (29.050 → 18.428), aunque sobre una base chica, contra −8,2 % del total.

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
| 2026 | 9 | 5 | 35.231 | 37,70 |
| 2025 | 9 | 16 | 222.524 | 33,99 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 5:00 en 2026 (US$ 37,70) y las 16:00 en 2025 (US$ 33,99). Es una hora de poco volumen (35.231 viajes, contra 233.026 a las 20:00, la hora pico de demanda). Gana porque a esa hora pesan los viajes largos: el 19,3 % de sus viajes toca JFK o LaGuardia (contra 8,3 % en todo el mes) y la distancia media es de 6,02 millas (contra 3,67).

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
| ALL ZONES |  | 3.667.332 | 2.780.820 | 75,83 |
| West Village | Manhattan | 79.922 | 79.850 | 99,91 |
| Greenwich Village South | Manhattan | 52.988 | 52.936 | 99,90 |
| East Village | Manhattan | 99.207 | 99.097 | 99,89 |
| SoHo | Manhattan | 32.803 | 32.766 | 99,89 |
| Lower East Side | Manhattan | 52.995 | 52.934 | 99,88 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 75,83 % de los viajes de septiembre 2026 pagó cbd_congestion_fee (2.780.820 de 3.667.332, siempre US$ 0,75). Las cinco zonas con mayor proporción (West Village, Greenwich Village South, East Village, SoHo y Lower East Side, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En septiembre 2025 lo pagaba el 74,01 % de los viajes: la proporción sube +1,8 pp. La regla R10 marcó 9.618 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 9 | 0 | Flex Fare | 1.078.694 | 1,30 | 1,00 |
| 2026 | 9 | 1 | Credit card | 2.266.594 | 24,79 | 22,14 |
| 2026 | 9 | 2 | Cash | 303.541 | 0,00 | 0,00 |
| 2026 | 9 | 3 | No charge | 6.074 | 0,00 | 0,00 |
| 2026 | 9 | 4 | Dispute | 11.017 | 0,01 | 0,01 |
| 2026 | 9 | 5 | Unknown | 2 | 27,30 | 25,55 |
| 2025 | 9 | 0 | Flex Fare | 827.190 | 1,44 | 1,49 |
| 2025 | 9 | 1 | Credit card | 2.605.862 | 25,82 | 21,39 |
| 2025 | 9 | 2 | Cash | 338.108 | 0,00 | 0,00 |
| 2025 | 9 | 3 | No charge | 14.000 | 0,08 | 0,03 |
| 2025 | 9 | 4 | Dispute | 52.082 | 0,05 | 0,04 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina baja: 24,79 % de la tarifa en 2026 frente a 25,82 % en 2025 (22,1 % y 21,4 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 24,7 % al 29,4 % de los viajes (827.190 → 1.078.694 con tarifa > 0) y cuya propina se mantiene en torno al 1,3 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 25,6 % al 31,0 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 65,2 % al 61,8 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 9 | 304.762 | 56,49 | 173.072 | 134.378 |
| 2025 | 9 | 336.219 | 58,25 | 197.728 | 141.541 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 9,4 % (336.219 → 304.762) mientras el total de la ciudad baja un 8,2 %, así que su peso cae del 8,4 % al 8,3 % de los viajes. Por aeropuerto, JFK cae −12,5 % y LaGuardia cae −5,1 %. La tarifa promedio baja de US$ 58,25 a US$ 56,49 (−3,0 %), pero esa baja está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 323.800,27 (de JFK Airport a Midtown South, 11,8 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 57,26 a US$ 56,46 (−1,4 %), y la mediana baja de US$ 58,30 a US$ 56,20. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.667.332 | 3.996.265 | -328.933 | -8,23 | 23,00 | 19,99 | 15,08 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Septiembre 2026 tuvo 3.667.332 viajes válidos contra 3.996.265 en septiembre 2025: −328.933 viajes (−8,23 %). La recaudación total (total_amount) crece un 2,4 %, de US$ 115,2 M a US$ 118,0 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario favorece a septiembre 2026: septiembre 2026 tuvo 5 miércoles, y septiembre 2025, 5 lunes (días flojos). Con el calendario de 2025 la variación sería −8,7 %. Todos los días de la semana caen (por día), entre −7 % y −12 %, así que la baja es general.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 15,08 % (de US$ 19,99 a US$ 23,00); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 323.800) la suba es del 15,6 % (de US$ 19,90 a US$ 23,00). La mediana pasa de US$ 14,90 a US$ 17,20 (+15,4 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de septiembre 2026 hay más viajes Flex Fare, que son más caros (US$ 29,42 contra US$ 20,32 del resto) y pasan del 25 % al 29 % de los viajes y menos viajes de más de 10 millas (del 8,3 % al 8,0 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 1,6 % (de US$ 20,65 a US$ 20,32).
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 5,99 % al 5,38 % de las filas leídas (208.712 filas en septiembre 2026 y 254.750 en septiembre 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,80 % contra 2,93 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,24 % contra 1,35 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en septiembre 2026 (−8,2 % de viajes, +2,4 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,8 %), Midtown Center (−13,0 %) y Midtown East (−13,1 %).
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 75,8 % de los viajes de septiembre 2026, contra 74,0 % en septiembre 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,67 contra 3,63 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,90 → US$ 17,20). La propina con tarjeta baja (25,8 % → 24,8 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Los promedios son frágiles: 58 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 323.800,27, en 2025) alcanzan para mover la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (septiembre 2026: columna nueva ignorada: request_source). La cuarentena es del 5,38 % y del 5,99 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-09 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-09`](http://localhost:8090/superset/dashboard/respaldo-local-2026-09/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 321 números en este reporte, 321 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:09 UTC, corrida `20261124T030441Z-aada0b`).

- Tablero `respaldo-local-2026-09`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.804 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 321 de 321 se ven en los charts que cita su bloque.
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
| Resumen | 3.667.332 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −8,2 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.996.265 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 118,0 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +2,4 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.876.044 | EC.1 | `filas_archivo` · 2026-09 (y 1 más) |
| Calidad | 3.876.044 | EC.1 | `filas_archivo` · 2026-09 (y 1 más) |
| Calidad | 3.667.332 | EC.1 | `aceptadas` · 2026-09 |
| Calidad | 208.712 | EC.1 | `cuarentena` · 2026-09 |
| Calidad | 5,38 | EC.1 | `pct_cuarentena` · 2026-09 |
| Calidad | 1.093.003 | EC.1 | `con_advertencias` · 2026-09 |
| Calidad | 28,20 | EC.1 | `pct_advertencias` · 2026-09 |
| Calidad | 4.251.015 | EC.1 | `filas_archivo` · 2025-09 (y 1 más) |
| Calidad | 4.251.015 | EC.1 | `filas_archivo` · 2025-09 (y 1 más) |
| Calidad | 3.996.265 | EC.1 | `aceptadas` · 2025-09 |
| Calidad | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Calidad | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Calidad | 1.010.489 | EC.1 | `con_advertencias` · 2025-09 |
| Calidad | 23,77 | EC.1 | `pct_advertencias` · 2025-09 |
| Calidad | 22 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 7 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 48.202 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,24 | EC.2 | `pct_mes` · R02 |
| Calidad | 57.179 | EC.2 | `filas_anterior` · R02 |
| Calidad | 1,35 | EC.2 | `pct_anterior` · R02 |
| Calidad | −0,10 | EC.2 | `cambio_pp` · R02 |
| Calidad | 147.283 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,80 | EC.2 | `pct_mes` · R03 |
| Calidad | 124.697 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,93 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,87 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.688 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,38 | EC.2 | `pct_mes` · R04 |
| Calidad | 78.492 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,85 | EC.2 | `pct_anterior` · R04 |
| Calidad | −1,47 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.200.950 | EC.2 | `filas_mes` · R05 |
| Calidad | 30,98 | EC.2 | `pct_mes` · R05 |
| Calidad | 1.089.381 | EC.2 | `filas_anterior` · R05 |
| Calidad | 25,63 | EC.2 | `pct_anterior` · R05 |
| Calidad | +5,36 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 18.461 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,48 | EC.2 | `pct_mes` · R08 |
| Calidad | 257.250 | EC.2 | `filas_anterior` · R08 |
| Calidad | 6,05 | EC.2 | `pct_anterior` · R08 |
| Calidad | −5,58 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.168 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | 1.216 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 9.618 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,25 | EC.2 | `pct_mes` · R10 |
| Calidad | 52.097 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,23 | EC.2 | `pct_anterior` · R10 |
| Calidad | −0,98 | EC.2 | `cambio_pp` · R10 |
| Calidad | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Calidad | 5,38 | EC.1 | `pct_cuarentena` · 2026-09 |
| Calidad | 208.712 | EC.1 | `cuarentena` · 2026-09 |
| Calidad | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Calidad | 3,80 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,93 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,24 | EC.2 | `pct_mes` · R02 |
| Calidad | 1,35 | EC.2 | `pct_anterior` · R02 |
| Calidad | −1,47 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.093.003 | EC.1 | `con_advertencias` · 2026-09 |
| Calidad | 28,2 | EC.1 | `pct_advertencias` · 2026-09 |
| Calidad | 31,0 | EC.2 | `pct_mes` · R05 |
| Calidad | 25,6 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 165.197 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 178.552 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | -13.355 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | -7,48 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 147.307 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 154.352 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | -7.045 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | -4,56 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 146.023 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 169.419 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -23.396 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -13,81 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 138.647 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 159.404 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -20.757 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -13,02 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 114.740 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 129.298 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -14.558 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -11,26 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 106.139 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 105.757 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 382 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 0,36 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 106.049 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 122.012 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -15.963 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -13,08 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 100.405 | E1.1 | `viajes_mes` · East Chelsea Manhattan |
| Pregunta 1 | 106.711 | E1.1 | `viajes_anterior` · East Chelsea Manhattan |
| Pregunta 1 | -6.306 | E1.1 | `variacion` · East Chelsea Manhattan |
| Pregunta 1 | -5,91 | E1.1 | `variacion_pct` · East Chelsea Manhattan |
| Pregunta 1 | 99.520 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 114.854 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -15.334 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -13,35 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 99.207 | E1.1 | `viajes_mes` · East Village Manhattan |
| Pregunta 1 | 102.998 | E1.1 | `viajes_anterior` · East Village Manhattan |
| Pregunta 1 | -3.791 | E1.1 | `variacion` · East Village Manhattan |
| Pregunta 1 | -3,68 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | −3,7 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | −13,8 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 165.197 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | −7,5 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 3 | E1.1 | `puesto_mes` · JFK Airport Queens (y 5 más) |
| Pregunta 1 | −13,8 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −7,2 | E1.5 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | −8,2 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 33,4 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 33,7 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | −36,6 | E1.6 | `variacion_pct` · Bronx |
| Pregunta 1 | 29.050 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 18.428 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −8,2 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `puesto_mes` · 0:00 (y 3 más) |
| Pregunta 2 | 35.231 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 37,70 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 16 | E2.1 | `puesto_mes` · 13:00 (y 3 más) |
| Pregunta 2 | 222.524 | E2.1 | `viajes_anterior` · 16:00 |
| Pregunta 2 | 33,99 | E2.1 | `ingreso_viaje_anterior` · 16:00 |
| Pregunta 2 | 5:00 | E2.1 | `puesto_mes` · 0:00 (y 13 más) |
| Pregunta 2 | 16:00 | E2.1 | `puesto_mes` · 13:00 (y 7 más) |
| Pregunta 2 | 20:00 | E2.1 | `puesto_mes` · 2:00 (y 5 más) |
| Pregunta 2 | 37,70 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 33,99 | E2.1 | `ingreso_viaje_anterior` · 16:00 (y 2 más) |
| Pregunta 2 | 35.231 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 233.026 | E2.1 | `viajes_mes` · 20:00 (y 1 más) |
| Pregunta 2 | 19,3 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,3 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 2 | 6,02 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,67 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 3 | 3.667.332 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.780.820 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 75,83 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 79.922 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 79.850 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,91 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 52.988 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 52.936 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,90 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99.207 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 99.097 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · East Village Manhattan (y 1 más) |
| Pregunta 3 | 32.803 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 32.766 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · East Village Manhattan (y 1 más) |
| Pregunta 3 | 52.995 | E3.3 | `viajes` · Lower East Side Manhattan |
| Pregunta 3 | 52.934 | E3.3 | `viajes_con_peaje` · Lower East Side Manhattan |
| Pregunta 3 | 99,88 | E3.3 | `pct_con_peaje` · Lower East Side Manhattan |
| Pregunta 3 | 75,83 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.780.820 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.667.332 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 4 más) |
| Pregunta 3 | 74,01 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | +1,8 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.618 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 1.078.694 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,30 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,00 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 2.266.594 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,79 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,14 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash (y 2 más) |
| Pregunta 4 | 303.541 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 6.074 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 11.017 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · Dispute (y 3 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · Dispute (y 3 más) |
| Pregunta 4 | 5 | E4.1 | `payment_type` · Unknown (y 1 más) |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash (y 2 más) |
| Pregunta 4 | 27,30 | E4.1 | `propina_media_pct_mes` · Unknown |
| Pregunta 4 | 25,55 | E4.1 | `propina_ponderada_pct_mes` · Unknown |
| Pregunta 4 | 827.190 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,44 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,49 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 2.605.862 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,82 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,39 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash (y 2 más) |
| Pregunta 4 | 338.108 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 7 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 14.000 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 52.082 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 24,79 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,82 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,1 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 21,4 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 91 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 24,7 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 29,4 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 827.190 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1.078.694 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,3 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 1 más) |
| Pregunta 4 | 25,6 | E4.1 | `propina_ponderada_pct_mes` · Unknown (y 1 más) |
| Pregunta 4 | 31,0 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 65,2 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 61,8 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 304.762 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,49 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 173.072 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 134.378 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 336.219 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 58,25 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 197.728 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 141.541 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 9,4 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 336.219 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 304.762 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 8,2 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 8,4 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,3 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −12,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −5,1 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 58,25 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 56,49 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −3,0 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 323.800,27 | E5.1 | `valor_anterior` · Tarifa máxima de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 11,8 | E5.4 | `distancia_millas` · 2025-09 Cash puesto 1 |
| Pregunta 5 | 57,26 | E5.1 | `valor_anterior` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 56,46 | E5.1 | `valor_mes` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | −1,4 | E5.1 | `variacion_pct` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 58,30 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 56,20 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.667.332 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.996.265 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -328.933 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -8,23 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 23,00 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,99 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 15,08 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.667.332 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.996.265 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −328.933 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −8,23 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 2,4 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 115,2 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 118,0 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 3 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 3 más) |
| Pregunta 6 | −8,7 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | −7 | E6.2 | `variacion_por_dia_pct` · martes (y 2 más) |
| Pregunta 6 | −12 | E6.2 | `variacion_por_dia_pct` · sábado |
| Pregunta 6 | 15,08 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 19,99 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 23,00 | E6.1 | `valor_mes` · Tarifa media (y 2 más) |
| Pregunta 6 | 323.800 | E6.1 | `valor_anterior` · Tarifa máxima (y 1 más) |
| Pregunta 6 | 15,6 | E6.1 | `variacion_pct` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 19,90 | E6.1 | `valor_anterior` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 23,00 | E6.1 | `valor_mes` · Tarifa media (y 2 más) |
| Pregunta 6 | 14,90 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 17,20 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +15,4 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 29,42 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,32 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 25 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 29 | E6.5 | `valor_mes` · Participación de Flex Fare (y 2 más) |
| Pregunta 6 | 8,3 | E6.5 | `valor_anterior` · Viajes de más de 10 millas (y 1 más) |
| Pregunta 6 | 8,0 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 1,6 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 20,65 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 20,32 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 5,99 | EC.1 | `pct_cuarentena` · 2025-09 |
| Pregunta 6 | 5,38 | EC.1 | `pct_cuarentena` · 2026-09 |
| Pregunta 6 | 208.712 | EC.1 | `cuarentena` · 2026-09 |
| Pregunta 6 | 254.750 | EC.1 | `cuarentena` · 2025-09 |
| Pregunta 6 | 3,80 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,93 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,24 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 1,35 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −8,2 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +2,4 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −13,8 | C1.2 | `variacion_pct` · JFK Airport Queens (y 1 más) |
| Conclusiones | −13,0 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | −13,1 | C1.2 | `variacion_pct` · Midtown East Manhattan |
| Conclusiones | 75,8 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 74,0 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,67 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,63 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,90 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 17,20 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,8 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 24,8 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 58 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses (y 1 más) |
| Conclusiones | 323.800,27 | C4.1 | `valor_anterior` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,38 | C5.1 | `pct_cuarentena` · 2026-09 |
| Conclusiones | 5,99 | C5.1 | `pct_cuarentena` · 2025-09 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-09/#CHART-C5-2
