# Resultados: abril 2026 vs abril 2025

> En abril 2026 los taxis amarillos hicieron 3.674.624 viajes válidos, −2,7 % que en abril 2025 (3.776.409), con una recaudación de US$ 110,6 M (+6,1 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-04 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-04.parquet` y `yellow_tripdata_2025-04.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-04`](http://localhost:8090/superset/dashboard/respaldo-local-2026-04/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=04/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-04 | `yellow_tripdata_2026-04.parquet` | 3.831.240 | 3.831.240 | 3.674.624 | 156.616 | 4,09 % | 755.063 (19,71 %) | sí |
| 2025-04 | `yellow_tripdata_2025-04.parquet` | 3.970.553 | 3.970.553 | 3.776.409 | 194.144 | 4,89 % | 721.657 (18,18 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-04 | 2025-04 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 12 (0,00 %) | 7 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 49.511 (1,29 %) | 34.769 (0,88 %) | +0,42 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 93.651 (2,44 %) | 91.745 (2,31 %) | +0,13 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.874 (0,39 %) | 72.608 (1,83 %) | −1,44 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 811.478 (21,18 %) | 768.831 (19,36 %) | +1,82 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 18.815 (0,49 %) | 191.095 (4,81 %) | −4,32 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.146 (0,03 %) | 1.095 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.706 (0,25 %) | 50.646 (1,28 %) | −1,02 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 4,89 % al 4,09 % de las filas leídas (156.616 filas en abril 2026 y 194.144 en abril 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,44 % contra 2,31 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 0,88 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,44 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 755.063 filas aceptadas de abril 2026 (19,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 21,2 %, contra 19,4 % en abril 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de abril 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de abril 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 176.545 | 178.609 | -2.064 | -1,16 |
| Manhattan | Midtown Center | 158.022 | 175.894 | -17.872 | -10,16 |
| Manhattan | Upper East Side North | 155.397 | 156.358 | -961 | -0,61 |
| Queens | JFK Airport | 142.773 | 145.700 | -2.927 | -2,01 |
| Manhattan | Midtown East | 113.886 | 119.413 | -5.527 | -4,63 |
| Manhattan | Penn Station/Madison Sq West | 113.449 | 121.862 | -8.413 | -6,90 |
| Manhattan | Times Sq/Theatre District | 109.583 | 127.528 | -17.945 | -14,07 |
| Manhattan | Lincoln Square East | 108.169 | 111.862 | -3.693 | -3,30 |
| Queens | LaGuardia Airport | 96.169 | 104.118 | -7.949 | -7,63 |
| Manhattan | Upper West Side South | 95.960 | 99.711 | -3.751 | -3,76 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan y las diez caen, entre −0,6 % (Upper East Side North) y −14,1 % (Times Sq/Theatre District). Upper East Side South lidera con 176.545 viajes (−1,2 %). Respecto de abril 2025 entra al top 10 Upper West Side South y sale Union Sq. En los aeropuertos, JFK (puesto 4 del top) cae −2,0 % y LaGuardia (puesto 9 del top) cae −7,6 %: LaGuardia va peor que el total de la ciudad y JFK queda en línea con él (−2,7 %). La demanda además se reparte más: el top 10 concentra el 34,6 % de los pickups, frente al 35,6 % de 2025. Fuera de Manhattan, el Bronx crece +23,6 % en sus pickups (28.212 → 34.866), aunque sobre una base chica, contra −2,7 % del total.

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
| 2026 | 4 | 5 | 31.310 | 36,04 |
| 2025 | 4 | 5 | 28.320 | 32,73 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,04 en 2026 y US$ 32,73 en 2025. Es una hora de poco volumen (31.310 viajes, contra 237.020 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 14,6 % de sus viajes toca JFK o LaGuardia (contra 8,0 % en todo el mes) y la distancia media es de 6,09 millas (contra 3,52). En 2026 la distancia media sube (de 5,75 a 6,09 millas), por eso el ingreso por viaje sube un 10,1 %, aunque los viajes de aeropuerto son menos (del 18,0 % al 14,6 % de los viajes de las 5:00).

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
| ALL ZONES |  | 3.674.624 | 2.636.125 | 71,74 |
| SoHo | Manhattan | 29.327 | 29.219 | 99,63 |
| Greenwich Village South | Manhattan | 53.378 | 53.172 | 99,61 |
| West Village | Manhattan | 80.551 | 80.185 | 99,55 |
| East Village | Manhattan | 93.429 | 92.843 | 99,37 |
| Midtown North | Manhattan | 93.339 | 92.733 | 99,35 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 71,74 % de los viajes de abril 2026 pagó cbd_congestion_fee (2.636.125 de 3.674.624, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Midtown North, alrededor del 99 %) están todas en Manhattan, dentro de la zona de peaje. En abril 2025 lo pagaba el 73,95 % de los viajes: la proporción baja −2,2 pp. La regla R10 marcó 9.706 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 4 | 0 | Flex Fare | 738.979 | 2,03 | 1,76 |
| 2026 | 4 | 1 | Credit card | 2.572.405 | 24,99 | 21,05 |
| 2026 | 4 | 2 | Cash | 342.739 | 0,00 | 0,00 |
| 2026 | 4 | 3 | No charge | 7.048 | 0,00 | 0,00 |
| 2026 | 4 | 4 | Dispute | 11.486 | 0,01 | 0,00 |
| 2025 | 4 | 0 | Flex Fare | 591.396 | 2,04 | 2,10 |
| 2025 | 4 | 1 | Credit card | 2.635.152 | 25,94 | 22,58 |
| 2025 | 4 | 2 | Cash | 382.522 | 0,00 | 0,00 |
| 2025 | 4 | 3 | No charge | 14.509 | 0,02 | 0,01 |
| 2025 | 4 | 4 | Dispute | 47.550 | 0,05 | 0,04 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina baja: 24,99 % de la tarifa en 2026 frente a 25,94 % en 2025 (21,1 % y 22,6 % ponderada), y deja propina el 90 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. También pesa Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 18,4 % al 20,1 % de los viajes (591.396 → 738.979 con tarifa > 0) y cuya propina se mantiene en torno al 2,0 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 19,4 % al 21,2 % de las filas leídas. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 4 | 292.622 | 55,29 | 166.688 | 128.230 |
| 2025 | 4 | 314.242 | 55,78 | 175.743 | 141.112 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 6,9 % (314.242 → 292.622) mientras el total de la ciudad baja un 2,7 %, así que su peso cae del 8,3 % al 8,0 % de los viajes. Por aeropuerto, JFK cae −5,2 % y LaGuardia cae −9,1 %. La tarifa promedio baja de US$ 55,78 a US$ 55,29 (−0,9 %), y la mediana baja de US$ 54,80 a US$ 53,40. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.674.624 | 3.776.409 | -101.785 | -2,70 | 21,08 | 18,65 | 13,01 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Abril 2026 tuvo 3.674.624 viajes válidos contra 3.776.409 en abril 2025: −101.785 viajes (−2,70 %). La recaudación total (total_amount) crece un 6,1 %, de US$ 104,2 M a US$ 110,6 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario casi no influye: abril 2026 tuvo 5 jueves (días fuertes), y abril 2025, 5 martes (días flojos). Por día de la semana la variación va de −7 % a +2 %: el cambio no es parejo.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 13,01 % (de US$ 18,65 a US$ 21,08). La mediana pasa de US$ 13,50 a US$ 15,60 (+15,6 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de abril 2026 hay más viajes Flex Fare, que son más caros (US$ 25,75 contra US$ 19,90 del resto) y pasan del 18 % al 20 % de los viajes, menos viajes a aeropuertos (del 8,3 % al 8,0 %) y más viajes de más de 10 millas (del 7,3 % al 7,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 4,6 % (de US$ 19,03 a US$ 19,90). El viaje promedio es más largo: 3,52 contra 3,37 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 4,89 % al 4,09 % de las filas leídas (156.616 filas en abril 2026 y 194.144 en abril 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,44 % contra 2,31 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 0,88 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae levemente en abril 2026 (−2,7 % de viajes, +6,1 % de recaudación). Las zonas que más pierden viajes son Times Sq/Theatre District (−14,1 %), Midtown Center (−10,2 %) y Midtown South (−12,1 %).
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 71,7 % de los viajes de abril 2026, contra 73,9 % en abril 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,52 contra 3,37 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 13,50 → US$ 15,60). La propina con tarjeta baja (25,9 % → 25,0 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 33 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 980,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 4,09 % y del 4,89 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-04 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-04`](http://localhost:8090/superset/dashboard/respaldo-local-2026-04/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 315 números en este reporte, 315 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:06 UTC, corrida `20261124T030441Z-aada0b`).

- Tablero `respaldo-local-2026-04`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.780 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 315 de 315 se ven en los charts que cita su bloque.
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
| Resumen | 3.674.624 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −2,7 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.776.409 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 110,6 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +6,1 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.831.240 | EC.1 | `filas_archivo` · 2026-04 (y 1 más) |
| Calidad | 3.831.240 | EC.1 | `filas_archivo` · 2026-04 (y 1 más) |
| Calidad | 3.674.624 | EC.1 | `aceptadas` · 2026-04 |
| Calidad | 156.616 | EC.1 | `cuarentena` · 2026-04 |
| Calidad | 4,09 | EC.1 | `pct_cuarentena` · 2026-04 |
| Calidad | 755.063 | EC.1 | `con_advertencias` · 2026-04 |
| Calidad | 19,71 | EC.1 | `pct_advertencias` · 2026-04 |
| Calidad | 3.970.553 | EC.1 | `filas_archivo` · 2025-04 (y 1 más) |
| Calidad | 3.970.553 | EC.1 | `filas_archivo` · 2025-04 (y 1 más) |
| Calidad | 3.776.409 | EC.1 | `aceptadas` · 2025-04 |
| Calidad | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Calidad | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Calidad | 721.657 | EC.1 | `con_advertencias` · 2025-04 |
| Calidad | 18,18 | EC.1 | `pct_advertencias` · 2025-04 |
| Calidad | 12 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 7 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 49.511 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,29 | EC.2 | `pct_mes` · R02 |
| Calidad | 34.769 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,88 | EC.2 | `pct_anterior` · R02 |
| Calidad | +0,42 | EC.2 | `cambio_pp` · R02 |
| Calidad | 93.651 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,44 | EC.2 | `pct_mes` · R03 |
| Calidad | 91.745 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,31 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,13 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.874 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,39 | EC.2 | `pct_mes` · R04 |
| Calidad | 72.608 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,83 | EC.2 | `pct_anterior` · R04 |
| Calidad | −1,44 | EC.2 | `cambio_pp` · R04 |
| Calidad | 811.478 | EC.2 | `filas_mes` · R05 |
| Calidad | 21,18 | EC.2 | `pct_mes` · R05 |
| Calidad | 768.831 | EC.2 | `filas_anterior` · R05 |
| Calidad | 19,36 | EC.2 | `pct_anterior` · R05 |
| Calidad | +1,82 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 18.815 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,49 | EC.2 | `pct_mes` · R08 |
| Calidad | 191.095 | EC.2 | `filas_anterior` · R08 |
| Calidad | 4,81 | EC.2 | `pct_anterior` · R08 |
| Calidad | −4,32 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.146 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | 1.095 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 9.706 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,25 | EC.2 | `pct_mes` · R10 |
| Calidad | 50.646 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,28 | EC.2 | `pct_anterior` · R10 |
| Calidad | −1,02 | EC.2 | `cambio_pp` · R10 |
| Calidad | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Calidad | 4,09 | EC.1 | `pct_cuarentena` · 2026-04 |
| Calidad | 156.616 | EC.1 | `cuarentena` · 2026-04 |
| Calidad | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Calidad | 2,44 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,31 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,29 | EC.2 | `pct_mes` · R02 |
| Calidad | 0,88 | EC.2 | `pct_anterior` · R02 |
| Calidad | −1,44 | EC.2 | `cambio_pp` · R04 |
| Calidad | 755.063 | EC.1 | `con_advertencias` · 2026-04 |
| Calidad | 19,7 | EC.1 | `pct_advertencias` · 2026-04 |
| Calidad | 21,2 | EC.2 | `pct_mes` · R05 |
| Calidad | 19,4 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 176.545 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 178.609 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | -2.064 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | -1,16 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 158.022 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 175.894 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -17.872 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -10,16 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 155.397 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 156.358 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | -961 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | -0,61 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 142.773 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 145.700 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -2.927 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -2,01 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 113.886 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 119.413 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -5.527 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -4,63 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 113.449 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 121.862 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -8.413 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -6,90 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 109.583 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 127.528 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -17.945 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -14,07 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 108.169 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 111.862 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -3.693 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -3,30 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 96.169 | E1.1 | `viajes_mes` · LaGuardia Airport Queens |
| Pregunta 1 | 104.118 | E1.1 | `viajes_anterior` · LaGuardia Airport Queens |
| Pregunta 1 | -7.949 | E1.1 | `variacion` · LaGuardia Airport Queens |
| Pregunta 1 | -7,63 | E1.1 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | 95.960 | E1.1 | `viajes_mes` · Upper West Side South Manhattan |
| Pregunta 1 | 99.711 | E1.1 | `viajes_anterior` · Upper West Side South Manhattan |
| Pregunta 1 | -3.751 | E1.1 | `variacion` · Upper West Side South Manhattan |
| Pregunta 1 | -3,76 | E1.1 | `variacion_pct` · Upper West Side South Manhattan |
| Pregunta 1 | −0,6 | E1.1 | `variacion_pct` · Upper East Side North Manhattan (y 1 más) |
| Pregunta 1 | −14,1 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan (y 1 más) |
| Pregunta 1 | 176.545 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | −1,2 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 4 | E1.1 | `puesto_mes` · JFK Airport Queens (y 8 más) |
| Pregunta 1 | −2,0 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 9 | E1.1 | `puesto_mes` · LaGuardia Airport Queens (y 8 más) |
| Pregunta 1 | −7,6 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | −2,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 34,6 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 35,6 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | +23,6 | E1.6 | `variacion_pct` · Bronx |
| Pregunta 1 | 28.212 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 34.866 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −2,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 4 más) |
| Pregunta 2 | 31.310 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 36,04 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 4 más) |
| Pregunta 2 | 28.320 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 32,73 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 14 más) |
| Pregunta 2 | 18:00 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 8 más) |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 14 más) |
| Pregunta 2 | 36,04 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 32,73 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 31.310 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 237.020 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 14,6 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,0 | E2.1 | `hora` · 8:00 (y 5 más) |
| Pregunta 2 | 6,09 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,52 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 5,75 | E2.6 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 6,09 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 10,1 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 1 más) |
| Pregunta 2 | 18,0 | E2.1 | `puesto_anterior` · 10:00 (y 7 más) |
| Pregunta 2 | 14,6 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 3 | 3.674.624 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.636.125 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 71,74 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 29.327 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 29.219 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,63 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 53.378 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 53.172 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,61 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 80.551 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 80.185 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,55 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 93.429 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 92.843 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,37 | E3.3 | `pct_con_peaje` · East Village Manhattan |
| Pregunta 3 | 93.339 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 92.733 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 99,35 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 71,74 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 (y 1 más) |
| Pregunta 3 | 2.636.125 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.674.624 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 99 | E3.3 | `pct_con_peaje` · East Village Manhattan (y 1 más) |
| Pregunta 3 | 73,95 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | −2,2 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.706 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 738.979 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,03 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,76 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.572.405 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,99 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,05 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 342.739 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 7.048 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 11.486 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,01 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 3 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 591.396 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 2,04 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,10 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.635.152 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,94 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,58 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 382.522 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 9 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 14.509 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 3 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 47.550 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_anterior` · Dispute (y 1 más) |
| Pregunta 4 | 24,99 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,94 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,1 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,6 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 90 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 18,4 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 20,1 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 591.396 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 738.979 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,0 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 4 más) |
| Pregunta 4 | 19,4 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 21,2 | E4.4 | `pct_mes` · R05 |
| Pregunta 5 | 292.622 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,29 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 166.688 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 128.230 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 314.242 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,78 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 175.743 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 141.112 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 6,9 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 314.242 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 292.622 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 2,7 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 8,3 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,0 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −5,2 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −9,1 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 55,78 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,29 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −0,9 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 54,80 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 53,40 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.674.624 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.776.409 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -101.785 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -2,70 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 21,08 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 18,65 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 13,01 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.674.624 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.776.409 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −101.785 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −2,70 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 6,1 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 104,2 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 110,6 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 4 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 4 más) |
| Pregunta 6 | −7 | E6.2 | `variacion_por_dia_pct` · viernes |
| Pregunta 6 | +2 | E6.2 | `variacion_por_dia_pct` · lunes (y 3 más) |
| Pregunta 6 | 13,01 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 18,65 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 21,08 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 13,50 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 15,60 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +15,6 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 25,75 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 19,90 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 18 | E6.5 | `valor_mes` · Duración media (y 1 más) |
| Pregunta 6 | 20 | E6.5 | `valor_mes` · Participación de Flex Fare (y 2 más) |
| Pregunta 6 | 8,3 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,0 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,3 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 7,9 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 4,6 | E6.5 | `variacion_pct` · Distancia media (y 2 más) |
| Pregunta 6 | 19,03 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 19,90 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 3,52 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,37 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Pregunta 6 | 4,09 | EC.1 | `pct_cuarentena` · 2026-04 |
| Pregunta 6 | 156.616 | EC.1 | `cuarentena` · 2026-04 |
| Pregunta 6 | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Pregunta 6 | 2,44 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,31 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,29 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 0,88 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −2,7 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +6,1 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −14,1 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | −10,2 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | −12,1 | C1.2 | `variacion_pct` · Midtown South Manhattan |
| Conclusiones | 71,7 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 73,9 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,52 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,37 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 13,50 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 15,60 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,9 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 25,0 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 33 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses (y 6 más) |
| Conclusiones | 980,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,09 | C5.1 | `pct_cuarentena` · 2026-04 |
| Conclusiones | 4,89 | C5.1 | `pct_cuarentena` · 2025-04 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-04/#CHART-C5-2
