# Resultados: agosto 2026 vs agosto 2025

> En agosto 2026 los taxis amarillos hicieron 3.163.698 viajes válidos, −5,3 % que en agosto 2025 (3.339.362), con una recaudación de US$ 95,4 M (+2,9 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-08 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-08.parquet` y `yellow_tripdata_2025-08.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-08`](http://localhost:8090/superset/dashboard/respaldo-local-2026-08/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=08/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-08 | `yellow_tripdata_2026-08.parquet` | 3.336.716 | 3.336.716 | 3.163.698 | 173.018 | 5,19 % | 849.450 (25,46 %) | sí |
| 2025-08 | `yellow_tripdata_2025-08.parquet` | 3.574.091 | 3.574.091 | 3.339.362 | 234.729 | 6,57 % | 831.289 (23,26 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-08 | 2025-08 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 15 (0,00 %) | 17 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 43.185 (1,29 %) | 47.833 (1,34 %) | −0,04 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 119.194 (3,57 %) | 105.429 (2,95 %) | +0,62 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.493 (0,43 %) | 87.940 (2,46 %) | −2,03 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 928.659 (27,83 %) | 903.506 (25,28 %) | +2,55 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 7 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 18.212 (0,55 %) | 265.314 (7,42 %) | −6,88 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 919 (0,03 %) | 1.070 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.520 (0,29 %) | 51.507 (1,44 %) | −1,16 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 6,57 % al 5,19 % de las filas leídas (173.018 filas en agosto 2026 y 234.729 en agosto 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,57 % contra 2,95 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 1,34 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −2,03 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 849.450 filas aceptadas de agosto 2026 (25,5 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 27,8 %, contra 25,3 % en agosto 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de agosto 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de agosto 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Queens | JFK Airport | 146.811 | 170.088 | -23.277 | -13,69 |
| Manhattan | Midtown Center | 130.701 | 137.058 | -6.357 | -4,64 |
| Manhattan | Upper East Side South | 122.556 | 120.393 | 2.163 | 1,80 |
| Manhattan | Penn Station/Madison Sq West | 111.890 | 113.281 | -1.391 | -1,23 |
| Manhattan | Upper East Side North | 100.019 | 97.952 | 2.067 | 2,11 |
| Manhattan | Midtown East | 95.902 | 102.370 | -6.468 | -6,32 |
| Manhattan | Times Sq/Theatre District | 92.680 | 101.953 | -9.273 | -9,10 |
| Manhattan | East Village | 90.901 | 87.277 | 3.624 | 4,15 |
| Manhattan | East Chelsea | 87.130 | 85.268 | 1.862 | 2,18 |
| Manhattan | Murray Hill | 85.509 | 92.827 | -7.318 | -7,88 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, cuatro crecen (entre +1,8 % en Upper East Side South y +4,2 % en East Village) y seis caen (entre −1,2 % en Penn Station/Madison Sq West y −13,7 % en JFK Airport). JFK Airport lidera con 146.811 viajes (−13,7 %). Respecto de agosto 2025 entra al top 10 East Chelsea y sale LaGuardia Airport. En los aeropuertos, JFK (puesto 1 del top) cae −13,7 % y LaGuardia (fuera del top) cae −9,7 %: los aeropuertos van peor que el total de la ciudad (−5,3 %). La concentración casi no cambia: el top 10 reúne el 33,6 % de los pickups (33,5 % en 2025). Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (30.287 → 13.805), aunque sobre una base chica, contra −5,3 % del total.

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
| 2026 | 8 | 5 | 31.232 | 33,67 |
| 2025 | 8 | 5 | 28.811 | 31,33 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,67 en 2026 y US$ 31,33 en 2025. Es una hora de poco volumen (31.232 viajes, contra 204.532 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,1 % de sus viajes toca JFK o LaGuardia (contra 9,0 % en todo el mes) y la distancia media es de 5,79 millas (contra 3,71). El ingreso por viaje de esa hora sube un 7,5 % aunque la distancia media baja (de 6,08 a 5,79 millas): lo explican las tarifas y recargos de 2026.

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
| ALL ZONES |  | 3.163.698 | 2.439.807 | 77,12 |
| West Village | Manhattan | 77.272 | 77.210 | 99,92 |
| Little Italy/NoLiTa | Manhattan | 36.580 | 36.541 | 99,89 |
| East Village | Manhattan | 90.901 | 90.802 | 99,89 |
| Greenwich Village South | Manhattan | 45.246 | 45.195 | 99,89 |
| Penn Station/Madison Sq West | Manhattan | 111.890 | 111.753 | 99,88 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 77,12 % de los viajes de agosto 2026 pagó cbd_congestion_fee (2.439.807 de 3.163.698, siempre US$ 0,75). Las cinco zonas con mayor proporción (West Village, Little Italy/NoLiTa, East Village, Greenwich Village South y Penn Station/Madison Sq West, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En agosto 2025 lo pagaba el 73,80 % de los viajes: la proporción sube +3,3 pp. La regla R10 marcó 9.520 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 8 | 0 | Flex Fare | 838.107 | 1,36 | 1,23 |
| 2026 | 8 | 1 | Credit card | 1.994.914 | 25,00 | 22,02 |
| 2026 | 8 | 2 | Cash | 312.570 | 0,00 | 0,00 |
| 2026 | 8 | 3 | No charge | 5.923 | 0,01 | 0,01 |
| 2026 | 8 | 4 | Dispute | 10.775 | 0,00 | 0,00 |
| 2025 | 8 | 0 | Flex Fare | 652.377 | 1,31 | 1,59 |
| 2025 | 8 | 1 | Credit card | 2.123.062 | 25,04 | 21,22 |
| 2025 | 8 | 2 | Cash | 338.269 | 0,00 | 0,00 |
| 2025 | 8 | 3 | No charge | 14.095 | 0,11 | 0,03 |
| 2025 | 8 | 4 | Dispute | 52.019 | 0,05 | 0,05 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 25,00 % de la tarifa en 2026 frente a 25,04 % en 2025 (22,0 % y 21,2 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 24,3 % al 26,5 % de los viajes (652.377 → 838.107 con tarifa > 0) y cuya propina se mantiene en torno al 1,4 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 25,3 % al 27,8 % de las filas leídas. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 8 | 285.907 | 54,39 | 171.457 | 117.621 |
| 2025 | 8 | 319.485 | 55,94 | 196.123 | 126.557 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 10,5 % (319.485 → 285.907) mientras el total de la ciudad baja un 5,3 %, así que su peso cae del 9,6 % al 9,0 % de los viajes. Por aeropuerto, JFK cae −12,6 % y LaGuardia cae −7,1 %. La tarifa promedio baja de US$ 55,94 a US$ 54,39 (−2,8 %), y la mediana baja de US$ 54,80 a US$ 50,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.163.698 | 3.339.362 | -175.664 | -5,26 | 21,11 | 19,09 | 10,59 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Agosto 2026 tuvo 3.163.698 viajes válidos contra 3.339.362 en agosto 2025: −175.664 viajes (−5,26 %). La recaudación total (total_amount) crece un 2,9 %, de US$ 92,7 M a US$ 95,4 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Parte de la caída es de calendario: agosto 2026 tuvo 5 lunes (días flojos), y agosto 2025, 5 viernes. Con el calendario de 2025 la variación sería −4,8 %. Por día de la semana la variación va de −12 % a +2 %: el cambio no es parejo.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 10,59 % (de US$ 19,09 a US$ 21,11). La mediana pasa de US$ 13,50 a US$ 15,60 (+15,6 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de agosto 2026 hay más viajes Flex Fare, que son más caros (US$ 24,89 contra US$ 19,74 del resto) y pasan del 24 % al 27 % de los viajes, menos viajes a aeropuertos (del 9,6 % al 9,0 %) y menos viajes de más de 10 millas (del 9,2 % al 8,1 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 3,5 % (de US$ 20,46 a US$ 19,74). El viaje promedio es más corto: 3,71 contra 3,83 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 6,57 % al 5,19 % de las filas leídas (173.018 filas en agosto 2026 y 234.729 en agosto 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,57 % contra 2,95 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 1,34 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en agosto 2026 (−5,3 % de viajes, +2,9 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,7 %), Times Sq/Theatre District (−9,1 %) y LaGuardia Airport (−9,7 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 77,1 % de los viajes de agosto 2026, contra 73,8 % en agosto 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más corto (3,71 contra 3,83 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 13,50 → US$ 15,60). La propina con tarjeta no se mueve (25,0 % → 25,0 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 80 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 950,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (agosto 2026: columna nueva ignorada: request_source). La cuarentena es del 5,19 % y del 6,57 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-08 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-08`](http://localhost:8090/superset/dashboard/respaldo-local-2026-08/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 314 números en este reporte, 314 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:08 UTC, corrida `20261124T030441Z-aada0b`).

- Tablero `respaldo-local-2026-08`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.798 celdas comparadas).
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
| Resumen | 3.163.698 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −5,3 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.339.362 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 95,4 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +2,9 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.336.716 | EC.1 | `filas_archivo` · 2026-08 (y 1 más) |
| Calidad | 3.336.716 | EC.1 | `filas_archivo` · 2026-08 (y 1 más) |
| Calidad | 3.163.698 | EC.1 | `aceptadas` · 2026-08 |
| Calidad | 173.018 | EC.1 | `cuarentena` · 2026-08 |
| Calidad | 5,19 | EC.1 | `pct_cuarentena` · 2026-08 |
| Calidad | 849.450 | EC.1 | `con_advertencias` · 2026-08 |
| Calidad | 25,46 | EC.1 | `pct_advertencias` · 2026-08 |
| Calidad | 3.574.091 | EC.1 | `filas_archivo` · 2025-08 (y 1 más) |
| Calidad | 3.574.091 | EC.1 | `filas_archivo` · 2025-08 (y 1 más) |
| Calidad | 3.339.362 | EC.1 | `aceptadas` · 2025-08 |
| Calidad | 234.729 | EC.1 | `cuarentena` · 2025-08 |
| Calidad | 6,57 | EC.1 | `pct_cuarentena` · 2025-08 |
| Calidad | 831.289 | EC.1 | `con_advertencias` · 2025-08 |
| Calidad | 23,26 | EC.1 | `pct_advertencias` · 2025-08 |
| Calidad | 15 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 17 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 43.185 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,29 | EC.2 | `pct_mes` · R02 |
| Calidad | 47.833 | EC.2 | `filas_anterior` · R02 |
| Calidad | 1,34 | EC.2 | `pct_anterior` · R02 |
| Calidad | −0,04 | EC.2 | `cambio_pp` · R02 |
| Calidad | 119.194 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,57 | EC.2 | `pct_mes` · R03 |
| Calidad | 105.429 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,95 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,62 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.493 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,43 | EC.2 | `pct_mes` · R04 |
| Calidad | 87.940 | EC.2 | `filas_anterior` · R04 |
| Calidad | 2,46 | EC.2 | `pct_anterior` · R04 |
| Calidad | −2,03 | EC.2 | `cambio_pp` · R04 |
| Calidad | 928.659 | EC.2 | `filas_mes` · R05 |
| Calidad | 27,83 | EC.2 | `pct_mes` · R05 |
| Calidad | 903.506 | EC.2 | `filas_anterior` · R05 |
| Calidad | 25,28 | EC.2 | `pct_anterior` · R05 |
| Calidad | +2,55 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 7 | EC.2 | `filas_mes` · R07 (y 2 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 18.212 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,55 | EC.2 | `pct_mes` · R08 |
| Calidad | 265.314 | EC.2 | `filas_anterior` · R08 |
| Calidad | 7,42 | EC.2 | `pct_anterior` · R08 |
| Calidad | −6,88 | EC.2 | `cambio_pp` · R08 |
| Calidad | 919 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | 1.070 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 9.520 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,29 | EC.2 | `pct_mes` · R10 |
| Calidad | 51.507 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,44 | EC.2 | `pct_anterior` · R10 |
| Calidad | −1,16 | EC.2 | `cambio_pp` · R10 |
| Calidad | 6,57 | EC.1 | `pct_cuarentena` · 2025-08 |
| Calidad | 5,19 | EC.1 | `pct_cuarentena` · 2026-08 |
| Calidad | 173.018 | EC.1 | `cuarentena` · 2026-08 |
| Calidad | 234.729 | EC.1 | `cuarentena` · 2025-08 |
| Calidad | 3,57 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,95 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,29 | EC.2 | `pct_mes` · R02 |
| Calidad | 1,34 | EC.2 | `pct_anterior` · R02 |
| Calidad | −2,03 | EC.2 | `cambio_pp` · R04 |
| Calidad | 849.450 | EC.1 | `con_advertencias` · 2026-08 |
| Calidad | 25,5 | EC.1 | `pct_advertencias` · 2026-08 |
| Calidad | 27,8 | EC.2 | `pct_mes` · R05 |
| Calidad | 25,3 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 146.811 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 170.088 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -23.277 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -13,69 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 130.701 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 137.058 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -6.357 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -4,64 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 122.556 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 120.393 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 2.163 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 1,80 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 111.890 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 113.281 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -1.391 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -1,23 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 100.019 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 97.952 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 2.067 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 2,11 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 95.902 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 102.370 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -6.468 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -6,32 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 92.680 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 101.953 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -9.273 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -9,10 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 90.901 | E1.1 | `viajes_mes` · East Village Manhattan |
| Pregunta 1 | 87.277 | E1.1 | `viajes_anterior` · East Village Manhattan |
| Pregunta 1 | 3.624 | E1.1 | `variacion` · East Village Manhattan |
| Pregunta 1 | 4,15 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | 87.130 | E1.1 | `viajes_mes` · East Chelsea Manhattan |
| Pregunta 1 | 85.268 | E1.1 | `viajes_anterior` · East Chelsea Manhattan |
| Pregunta 1 | 1.862 | E1.1 | `variacion` · East Chelsea Manhattan |
| Pregunta 1 | 2,18 | E1.1 | `variacion_pct` · East Chelsea Manhattan |
| Pregunta 1 | 85.509 | E1.1 | `viajes_mes` · Murray Hill Manhattan |
| Pregunta 1 | 92.827 | E1.1 | `viajes_anterior` · Murray Hill Manhattan |
| Pregunta 1 | -7.318 | E1.1 | `variacion` · Murray Hill Manhattan |
| Pregunta 1 | -7,88 | E1.1 | `variacion_pct` · Murray Hill Manhattan |
| Pregunta 1 | +1,8 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +4,2 | E1.1 | `variacion_pct` · East Village Manhattan (y 1 más) |
| Pregunta 1 | −1,2 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan (y 1 más) |
| Pregunta 1 | −13,7 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 146.811 | E1.1 | `viajes_mes` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −13,7 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 1 | E1.1 | `puesto_mes` · JFK Airport Queens (y 18 más) |
| Pregunta 1 | −13,7 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −9,7 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | −5,3 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 33,6 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 33,5 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 30.287 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 13.805 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −5,3 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `puesto_mes` · 0:00 (y 2 más) |
| Pregunta 2 | 31.232 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 33,67 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `puesto_mes` · 0:00 (y 2 más) |
| Pregunta 2 | 28.811 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 31,33 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `puesto_mes` · 0:00 (y 14 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 7:00 (y 7 más) |
| Pregunta 2 | 33,67 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 31,33 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 31.232 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 204.532 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 18,1 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 9,0 | E2.1 | `puesto_anterior` · 6:00 (y 5 más) |
| Pregunta 2 | 5,79 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,71 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 7,5 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 2 más) |
| Pregunta 2 | 6,08 | E2.6 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 5,79 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 3 | 3.163.698 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.439.807 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 77,12 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 77.272 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 77.210 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,92 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 36.580 | E3.3 | `viajes` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 36.541 | E3.3 | `viajes_con_peaje` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · Little Italy/NoLiTa Manhattan (y 2 más) |
| Pregunta 3 | 90.901 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 90.802 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · Little Italy/NoLiTa Manhattan (y 2 más) |
| Pregunta 3 | 45.246 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 45.195 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · Little Italy/NoLiTa Manhattan (y 2 más) |
| Pregunta 3 | 111.890 | E3.3 | `viajes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 111.753 | E3.3 | `viajes_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 99,88 | E3.3 | `pct_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 77,12 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.439.807 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.163.698 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 4 más) |
| Pregunta 3 | 73,80 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | +3,3 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.520 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 838.107 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,36 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,23 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 4 más) |
| Pregunta 4 | 1.994.914 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 25,00 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,02 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 2 más) |
| Pregunta 4 | 312.570 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 5.923 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 3 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 3 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 10.775 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 652.377 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,31 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,59 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 4 más) |
| Pregunta 4 | 2.123.062 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,04 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,22 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 2 más) |
| Pregunta 4 | 338.269 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge (y 1 más) |
| Pregunta 4 | 14.095 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,11 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 52.019 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute (y 1 más) |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_anterior` · Dispute (y 1 más) |
| Pregunta 4 | 25,00 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,04 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,0 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 21,2 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 91 | E4.5 | `pct_con_propina_mes` · Credit card (y 1 más) |
| Pregunta 4 | 24,3 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 26,5 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 652.377 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 838.107 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,4 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 25,3 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 27,8 | E4.4 | `pct_mes` · R05 |
| Pregunta 5 | 285.907 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 54,39 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 171.457 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 117.621 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 319.485 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,94 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 196.123 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 126.557 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 10,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 319.485 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 285.907 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 5,3 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,6 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 9,0 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −12,6 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −7,1 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 55,94 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 54,39 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −2,8 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 54,80 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 50,60 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.163.698 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.339.362 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -175.664 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -5,26 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 21,11 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,09 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 10,59 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.163.698 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.339.362 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −175.664 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −5,26 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 2,9 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 92,7 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 95,4 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 9 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 9 más) |
| Pregunta 6 | −4,8 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | −12 | E6.2 | `variacion_por_dia_pct` · miércoles |
| Pregunta 6 | +2 | E6.2 | `variacion_por_dia_pct` · jueves (y 3 más) |
| Pregunta 6 | 10,59 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 19,09 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 21,11 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 13,50 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 15,60 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +15,6 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 24,89 | E6.5 | `valor_mes` · Tarifa media Flex Fare, sin tarifas mayores a US$ 500 |
| Pregunta 6 | 19,74 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 24 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 27 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 9,6 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 9,0 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 9,2 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 8,1 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 3,5 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 20,46 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 19,74 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,71 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,83 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 6,57 | EC.1 | `pct_cuarentena` · 2025-08 |
| Pregunta 6 | 5,19 | EC.1 | `pct_cuarentena` · 2026-08 |
| Pregunta 6 | 173.018 | EC.1 | `cuarentena` · 2026-08 |
| Pregunta 6 | 234.729 | EC.1 | `cuarentena` · 2025-08 |
| Pregunta 6 | 3,57 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,95 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,29 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 1,34 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −5,3 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +2,9 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −13,7 | C1.2 | `variacion_pct` · JFK Airport Queens (y 1 más) |
| Conclusiones | −9,1 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | −9,7 | C1.2 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Conclusiones | 77,1 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 73,8 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,71 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,83 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 13,50 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 15,60 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,0 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito (y 1 más) |
| Conclusiones | 25,0 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito (y 1 más) |
| Conclusiones | 80 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 950,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,19 | C5.1 | `pct_cuarentena` · 2026-08 |
| Conclusiones | 6,57 | C5.1 | `pct_cuarentena` · 2025-08 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-08/#CHART-C5-2
