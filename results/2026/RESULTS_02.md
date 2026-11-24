# Resultados: febrero 2026 vs febrero 2025

> En febrero 2026 los taxis amarillos hicieron 3.210.995 viajes válidos, −6,1 % que en febrero 2025 (3.421.132), con una recaudación de US$ 97,8 M (+10,4 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-02 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-02.parquet` y `yellow_tripdata_2025-02.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-02`](http://localhost:8090/superset/dashboard/respaldo-local-2026-02/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=02/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-02 | `yellow_tripdata_2026-02.parquet` | 3.399.866 | 3.399.866 | 3.210.995 | 188.871 | 5,56 % | 943.856 (27,76 %) | sí |
| 2025-02 | `yellow_tripdata_2025-02.parquet` | 3.577.543 | 3.577.543 | 3.421.132 | 156.411 | 4,37 % | 767.302 (21,45 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-02 | 2025-02 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 16 (0,00 %) | 31 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 40.598 (1,19 %) | 5.164 (0,14 %) | +1,05 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 123.422 (3,63 %) | 99.943 (2,79 %) | +0,84 pp |
| R04 | reject | Total cobrado faltante o negativo. | 27.291 (0,80 %) | 55.179 (1,54 %) | −0,74 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.036.201 (30,48 %) | 828.688 (23,16 %) | +7,31 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 30.449 (0,90 %) | 186.623 (5,22 %) | −4,32 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 762 (0,02 %) | 841 (0,02 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 17.479 (0,51 %) | 37.238 (1,04 %) | −0,53 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 4,37 % al 5,56 % de las filas leídas (188.871 filas en febrero 2026 y 156.411 en febrero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,63 % contra 2,79 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,19 % contra 0,14 %).
- Las reglas de advertencia no sacan filas: 943.856 filas aceptadas de febrero 2026 (27,8 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 30,5 %, contra 23,2 % en febrero 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de febrero 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de febrero 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 138.289 | 152.770 | -14.481 | -9,48 |
| Manhattan | Upper East Side North | 131.418 | 143.712 | -12.294 | -8,55 |
| Manhattan | Midtown Center | 128.649 | 155.533 | -26.884 | -17,29 |
| Queens | JFK Airport | 116.974 | 115.233 | 1.741 | 1,51 |
| Manhattan | Midtown East | 94.729 | 109.808 | -15.079 | -13,73 |
| Manhattan | Penn Station/Madison Sq West | 94.276 | 109.148 | -14.872 | -13,63 |
| Manhattan | East Village | 90.240 | 93.197 | -2.957 | -3,17 |
| Manhattan | Lincoln Square East | 89.942 | 101.271 | -11.329 | -11,19 |
| Manhattan | Times Sq/Theatre District | 86.595 | 109.839 | -23.244 | -21,16 |
| Manhattan | Union Sq | 84.896 | 98.966 | -14.070 | -14,22 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, una crece (+1,5 % en JFK Airport) y nueve caen (entre −3,2 % en East Village y −21,2 % en Times Sq/Theatre District). Upper East Side South lidera con 138.289 viajes (−9,5 %) y desplaza a Midtown Center, que encabezaba febrero 2025. En los aeropuertos, JFK (puesto 4 del top) crece +1,5 % y LaGuardia (fuera del top) cae −10,3 %: LaGuardia va peor que el total de la ciudad y JFK va mejor (−6,1 %). La demanda además se reparte más: el top 10 concentra el 32,9 % de los pickups, frente al 34,8 % de 2025. Fuera de Manhattan, el Bronx crece +65,3 % en sus pickups (20.022 → 33.089), aunque sobre una base chica, contra −6,1 % del total.

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
| 2026 | 2 | 5 | 30.568 | 36,52 |
| 2025 | 2 | 5 | 23.365 | 32,29 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,52 en 2026 y US$ 32,29 en 2025. Es una hora de poco volumen (30.568 viajes, contra 220.354 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 13,8 % de sus viajes toca JFK o LaGuardia (contra 7,1 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,43). El ingreso por viaje de esa hora sube un 13,1 % aunque los viajes de aeropuerto son menos (del 18,2 % al 13,8 % de los viajes de las 5:00): lo explican las tarifas y recargos de 2026.

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
| ALL ZONES |  | 3.210.995 | 2.277.558 | 70,93 |
| SoHo | Manhattan | 24.968 | 24.903 | 99,74 |
| Greenwich Village South | Manhattan | 47.321 | 47.171 | 99,68 |
| West Village | Manhattan | 71.603 | 71.371 | 99,68 |
| East Village | Manhattan | 90.240 | 89.845 | 99,56 |
| Midtown North | Manhattan | 75.634 | 75.287 | 99,54 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 70,93 % de los viajes de febrero 2026 pagó cbd_congestion_fee (2.277.558 de 3.210.995, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Midtown North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En febrero 2025 lo pagaba el 74,09 % de los viajes: la proporción baja −3,2 pp. La regla R10 marcó 17.479 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 2 | 0 | Flex Fare | 928.164 | 1,88 | 1,55 |
| 2026 | 2 | 1 | Credit card | 2.000.161 | 24,80 | 21,15 |
| 2026 | 2 | 2 | Cash | 255.450 | 0,00 | 0,00 |
| 2026 | 2 | 3 | No charge | 6.704 | 0,01 | 0,01 |
| 2026 | 2 | 4 | Dispute | 19.061 | 0,01 | 0,03 |
| 2025 | 2 | 0 | Flex Fare | 628.164 | 1,90 | 2,00 |
| 2025 | 2 | 1 | Credit card | 2.312.981 | 26,35 | 22,87 |
| 2025 | 2 | 2 | Cash | 317.947 | 0,00 | 0,00 |
| 2025 | 2 | 3 | No charge | 11.348 | 0,43 | 0,12 |
| 2025 | 2 | 4 | Dispute | 35.028 | 0,08 | 0,09 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina baja: 24,80 % de la tarifa en 2026 frente a 26,35 % en 2025 (21,2 % y 22,9 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 21,7 % al 28,9 % de los viajes (628.164 → 928.164 con tarifa > 0) y cuya propina se mantiene en torno al 1,9 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 23,2 % al 30,5 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 67,6 % al 62,3 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 2 | 229.500 | 55,58 | 134.384 | 96.976 |
| 2025 | 2 | 242.974 | 54,31 | 135.405 | 109.694 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 5,5 % (242.974 → 229.500) mientras el total de la ciudad baja un 6,1 %, así que su peso se mantiene en el 7,1 % de los viajes. Por aeropuerto, JFK cae −0,8 % y LaGuardia cae −11,6 %. La tarifa promedio sube de US$ 54,31 a US$ 55,58 (+2,3 %), y la mediana sube de US$ 51,30 a US$ 54,10. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.210.995 | 3.421.132 | -210.137 | -6,14 | 21,79 | 17,31 | 25,91 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Febrero 2026 tuvo 3.210.995 viajes válidos contra 3.421.132 en febrero 2025: −210.137 viajes (−6,14 %). La recaudación total (total_amount) crece un 10,4 %, de US$ 88,5 M a US$ 97,8 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Los dos meses tienen la misma composición de días de la semana, así que no hay efecto calendario. Todos los días de la semana caen (por día), entre −3 % y −18 %, así que la baja es general.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 25,91 % (de US$ 17,31 a US$ 21,79). La mediana pasa de US$ 12,80 a US$ 16,30 (+27,3 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de febrero 2026 hay más viajes Flex Fare, que son más caros (US$ 27,09 contra US$ 19,63 del resto) y pasan del 22 % al 29 % de los viajes y más viajes de más de 10 millas (del 6,1 % al 7,4 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 10,4 % (de US$ 17,79 a US$ 19,63). El viaje promedio es más largo: 3,43 contra 3,12 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 4,37 % al 5,56 % de las filas leídas (188.871 filas en febrero 2026 y 156.411 en febrero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,63 % contra 2,79 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,19 % contra 0,14 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en febrero 2026 (−6,1 % de viajes, +10,4 % de recaudación). Las zonas que más pierden viajes son Midtown Center (−17,3 %), Times Sq/Theatre District (−21,2 %) y Midtown North (−16,8 %).
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 70,9 % de los viajes de febrero 2026, contra 74,1 % en febrero 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,43 contra 3,12 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 12,80 → US$ 16,30). La propina con tarjeta baja (26,4 % → 24,8 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 38 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 132.531,36, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 5,56 % y del 4,37 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-02 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-02`](http://localhost:8090/superset/dashboard/respaldo-local-2026-02/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 309 números en este reporte, 309 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:05 UTC, corrida `20261124T030441Z-aada0b`).

- Tablero `respaldo-local-2026-02`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.728 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 309 de 309 se ven en los charts que cita su bloque.
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
| Resumen | 3.210.995 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −6,1 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.421.132 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 97,8 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +10,4 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.399.866 | EC.1 | `filas_archivo` · 2026-02 (y 1 más) |
| Calidad | 3.399.866 | EC.1 | `filas_archivo` · 2026-02 (y 1 más) |
| Calidad | 3.210.995 | EC.1 | `aceptadas` · 2026-02 |
| Calidad | 188.871 | EC.1 | `cuarentena` · 2026-02 |
| Calidad | 5,56 | EC.1 | `pct_cuarentena` · 2026-02 |
| Calidad | 943.856 | EC.1 | `con_advertencias` · 2026-02 |
| Calidad | 27,76 | EC.1 | `pct_advertencias` · 2026-02 |
| Calidad | 3.577.543 | EC.1 | `filas_archivo` · 2025-02 (y 1 más) |
| Calidad | 3.577.543 | EC.1 | `filas_archivo` · 2025-02 (y 1 más) |
| Calidad | 3.421.132 | EC.1 | `aceptadas` · 2025-02 |
| Calidad | 156.411 | EC.1 | `cuarentena` · 2025-02 |
| Calidad | 4,37 | EC.1 | `pct_cuarentena` · 2025-02 |
| Calidad | 767.302 | EC.1 | `con_advertencias` · 2025-02 |
| Calidad | 21,45 | EC.1 | `pct_advertencias` · 2025-02 |
| Calidad | 16 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 31 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 40.598 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,19 | EC.2 | `pct_mes` · R02 |
| Calidad | 5.164 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,14 | EC.2 | `pct_anterior` · R02 |
| Calidad | +1,05 | EC.2 | `cambio_pp` · R02 |
| Calidad | 123.422 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,63 | EC.2 | `pct_mes` · R03 |
| Calidad | 99.943 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,79 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,84 | EC.2 | `cambio_pp` · R03 |
| Calidad | 27.291 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,80 | EC.2 | `pct_mes` · R04 |
| Calidad | 55.179 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,54 | EC.2 | `pct_anterior` · R04 |
| Calidad | −0,74 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.036.201 | EC.2 | `filas_mes` · R05 |
| Calidad | 30,48 | EC.2 | `pct_mes` · R05 |
| Calidad | 828.688 | EC.2 | `filas_anterior` · R05 |
| Calidad | 23,16 | EC.2 | `pct_anterior` · R05 |
| Calidad | +7,31 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 30.449 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,90 | EC.2 | `pct_mes` · R08 |
| Calidad | 186.623 | EC.2 | `filas_anterior` · R08 |
| Calidad | 5,22 | EC.2 | `pct_anterior` · R08 |
| Calidad | −4,32 | EC.2 | `cambio_pp` · R08 |
| Calidad | 762 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,02 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | 841 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,02 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 13 más) |
| Calidad | 17.479 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,51 | EC.2 | `pct_mes` · R10 |
| Calidad | 37.238 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,04 | EC.2 | `pct_anterior` · R10 |
| Calidad | −0,53 | EC.2 | `cambio_pp` · R10 |
| Calidad | 4,37 | EC.1 | `pct_cuarentena` · 2025-02 |
| Calidad | 5,56 | EC.1 | `pct_cuarentena` · 2026-02 |
| Calidad | 188.871 | EC.1 | `cuarentena` · 2026-02 |
| Calidad | 156.411 | EC.1 | `cuarentena` · 2025-02 |
| Calidad | 3,63 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,79 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,19 | EC.2 | `pct_mes` · R02 |
| Calidad | 0,14 | EC.2 | `pct_anterior` · R02 |
| Calidad | 943.856 | EC.1 | `con_advertencias` · 2026-02 |
| Calidad | 27,8 | EC.1 | `pct_advertencias` · 2026-02 |
| Calidad | 30,5 | EC.2 | `pct_mes` · R05 |
| Calidad | 23,2 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 138.289 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 152.770 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | -14.481 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | -9,48 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 131.418 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 143.712 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | -12.294 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | -8,55 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 128.649 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 155.533 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -26.884 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -17,29 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 116.974 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 115.233 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | 1.741 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | 1,51 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 94.729 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 109.808 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -15.079 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -13,73 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 94.276 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 109.148 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -14.872 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -13,63 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 90.240 | E1.1 | `viajes_mes` · East Village Manhattan |
| Pregunta 1 | 93.197 | E1.1 | `viajes_anterior` · East Village Manhattan |
| Pregunta 1 | -2.957 | E1.1 | `variacion` · East Village Manhattan |
| Pregunta 1 | -3,17 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | 89.942 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 101.271 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -11.329 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -11,19 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 86.595 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 109.839 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -23.244 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -21,16 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 84.896 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 98.966 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | -14.070 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | -14,22 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | +1,5 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −3,2 | E1.1 | `variacion_pct` · East Village Manhattan (y 1 más) |
| Pregunta 1 | −21,2 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan (y 1 más) |
| Pregunta 1 | 138.289 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | −9,5 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 4 | E1.1 | `puesto_mes` · JFK Airport Queens (y 7 más) |
| Pregunta 1 | +1,5 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −10,3 | E1.5 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | −6,1 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 32,9 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 34,8 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | +65,3 | E1.6 | `variacion_pct` · Bronx |
| Pregunta 1 | 20.022 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 33.089 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −6,1 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 2 más) |
| Pregunta 2 | 30.568 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 36,52 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 2 más) |
| Pregunta 2 | 23.365 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 32,29 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 12 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 3:00 (y 8 más) |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 12 más) |
| Pregunta 2 | 36,52 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 32,29 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 30.568 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 220.354 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 13,8 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 7,1 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto (y 3 más) |
| Pregunta 2 | 5,71 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,43 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 13,1 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 1 más) |
| Pregunta 2 | 18,2 | E2.6 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 13,8 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 3 | 3.210.995 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.277.558 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 70,93 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 24.968 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 24.903 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,74 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 47.321 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 47.171 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,68 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 71.603 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 71.371 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,68 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 90.240 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 89.845 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,56 | E3.3 | `pct_con_peaje` · East Village Manhattan |
| Pregunta 3 | 75.634 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 75.287 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 99,54 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 70,93 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.277.558 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.210.995 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 4 más) |
| Pregunta 3 | 74,09 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | −3,2 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 (y 1 más) |
| Pregunta 3 | 17.479 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 928.164 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,88 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,55 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.000.161 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,80 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,15 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 255.450 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 6.704 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 5 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 5 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 19.061 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 5 más) |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_mes` · Dispute |
| Pregunta 4 | 628.164 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,90 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,00 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 2 más) |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.312.981 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 26,35 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,87 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 317.947 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 11.348 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,43 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,12 | E4.1 | `propina_ponderada_pct_anterior` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 35.028 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · Dispute |
| Pregunta 4 | 0,09 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 24,80 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 26,35 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,2 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,9 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 91 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 21,7 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 28,9 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 628.164 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 928.164 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,9 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 1 más) |
| Pregunta 4 | 23,2 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 30,5 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 67,6 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 62,3 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 229.500 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,58 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 134.384 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 96.976 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 242.974 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 54,31 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 135.405 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 109.694 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 5,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia (y 1 más) |
| Pregunta 5 | 242.974 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 229.500 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 6,1 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 7,1 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | −0,8 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −11,6 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 54,31 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,58 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | +2,3 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 51,30 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 54,10 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.210.995 | E6.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 6 | 3.421.132 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -210.137 | E6.1 | `variacion` · Viajes válidos (y 1 más) |
| Pregunta 6 | -6,14 | E6.1 | `variacion_pct` · Viajes válidos (y 1 más) |
| Pregunta 6 | 21,79 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 17,31 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 25,91 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.210.995 | E6.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 6 | 3.421.132 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −210.137 | E6.1 | `variacion` · Viajes válidos (y 1 más) |
| Pregunta 6 | −6,14 | E6.1 | `variacion_pct` · Viajes válidos (y 1 más) |
| Pregunta 6 | 10,4 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 88,5 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 97,8 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | −3 | E6.2 | `variacion_por_dia_pct` · miércoles |
| Pregunta 6 | −18 | E6.2 | `variacion_por_dia_pct` · lunes |
| Pregunta 6 | 25,91 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 17,31 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 21,79 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 12,80 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 16,30 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +27,3 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 27,09 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 19,63 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 22 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 29 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 6,1 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 7,4 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 10,4 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 17,79 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 19,63 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,43 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,12 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 4,37 | EC.1 | `pct_cuarentena` · 2025-02 |
| Pregunta 6 | 5,56 | EC.1 | `pct_cuarentena` · 2026-02 |
| Pregunta 6 | 188.871 | EC.1 | `cuarentena` · 2026-02 |
| Pregunta 6 | 156.411 | EC.1 | `cuarentena` · 2025-02 |
| Pregunta 6 | 3,63 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,79 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,19 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 0,14 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −6,1 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +10,4 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −17,3 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | −21,2 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | −16,8 | C1.2 | `variacion_pct` · Midtown North Manhattan (y 1 más) |
| Conclusiones | 70,9 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 74,1 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,43 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,12 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 12,80 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 16,30 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 26,4 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 24,8 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 38 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 132.531,36 | C4.1 | `valor_anterior` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,56 | C5.1 | `pct_cuarentena` · 2026-02 |
| Conclusiones | 4,37 | C5.1 | `pct_cuarentena` · 2025-02 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-02/#CHART-C5-2
