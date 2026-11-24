# Resultados: enero 2025 vs enero 2024

> En enero 2025 los taxis amarillos hicieron 3.323.437 viajes válidos, +15,8 % que en enero 2024 (2.870.896), con una recaudación de US$ 88,3 M (+12,7 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-01 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-01.parquet` y `yellow_tripdata_2024-01.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-01`](http://localhost:8090/superset/dashboard/respaldo-local-2025-01/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=01/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-01 | `yellow_tripdata_2025-01.parquet` | 3.475.226 | 3.475.226 | 3.323.437 | 151.789 | 4,37 % | 511.679 (14,72 %) | sí |
| 2024-01 | `yellow_tripdata_2024-01.parquet` | 2.964.624 | 2.964.624 | 2.870.896 | 93.728 | 3,16 % | 150.746 (5,08 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-01 | 2024-01 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 22 (0,00 %) | 18 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 2.051 (0,06 %) | 870 (0,03 %) | +0,03 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 91.055 (2,62 %) | 60.430 (2,04 %) | +0,58 pp |
| R04 | reject | Total cobrado faltante o negativo. | 63.037 (1,81 %) | 35.504 (1,20 %) | +0,62 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 564.805 (16,25 %) | 171.627 (5,79 %) | +10,46 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 148.413 (4,27 %) | 41.402 (1,40 %) | +2,87 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 982 (0,03 %) | 1.107 (0,04 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 6.954 (0,20 %) | 0 (0,00 %) | +0,20 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 3,16 % al 4,37 % de las filas leídas (151.789 filas en enero 2025 y 93.728 en enero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 2,04 %) y R04 (total cobrado faltante o negativo: 1,81 % contra 1,20 %).
- Las reglas de advertencia no sacan filas: 511.679 filas aceptadas de enero 2025 (14,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 16,3 %, contra 5,8 % en enero 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de enero 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de enero 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Midtown Center | 163.866 | 140.220 | 23.646 | 16,86 |
| Manhattan | Upper East Side South | 159.330 | 140.160 | 19.170 | 13,68 |
| Manhattan | Upper East Side North | 151.616 | 134.027 | 17.589 | 13,12 |
| Queens | JFK Airport | 134.804 | 138.341 | -3.537 | -2,56 |
| Manhattan | Times Sq/Theatre District | 120.657 | 102.999 | 17.658 | 17,14 |
| Manhattan | Penn Station/Madison Sq West | 115.021 | 102.165 | 12.856 | 12,58 |
| Manhattan | Midtown East | 113.840 | 104.374 | 9.466 | 9,07 |
| Manhattan | Lincoln Square East | 107.540 | 101.847 | 5.693 | 5,59 |
| Manhattan | Upper West Side South | 93.831 | 86.532 | 7.299 | 8,44 |
| Manhattan | Midtown North | 92.702 | 83.711 | 8.991 | 10,74 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +5,6 % en Lincoln Square East y +17,1 % en Times Sq/Theatre District) y una cae (JFK Airport −2,6 %). Midtown Center lidera con 163.866 viajes (+16,9 %). Respecto de enero 2024 entra al top 10 Midtown North y sale LaGuardia Airport. En los aeropuertos, JFK (puesto 4 del top) cae −2,6 % y LaGuardia (fuera del top) cae −1,4 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 37,7 % de los pickups, frente al 39,7 % de 2024. Fuera de Manhattan, Brooklyn casi triplica sus pickups (22.286 → 60.244), aunque sobre una base chica, contra +15,8 % del total.

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
| 2025 | 1 | 5 | 21.233 | 33,64 |
| 2024 | 1 | 5 | 17.490 | 37,54 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,64 en 2025 y US$ 37,54 en 2024. Es una hora de poco volumen (21.233 viajes, contra 242.182 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 20,8 % de sus viajes toca JFK o LaGuardia (contra 8,2 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,16). En 2025 los viajes de aeropuerto son menos (del 25,8 % al 20,8 % de los viajes de las 5:00) y la distancia media baja (de 6,23 a 5,71 millas), por eso el ingreso por viaje cae un 10,4 %. Ojo con el segundo puesto de 2025 (las 12:00, US$ 30,68): es artificial, porque lo infla un viaje con una tarifa de US$ 863.372,12. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 25,59.

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
| ALL ZONES |  | 3.323.437 | 2.192.727 | 65,98 |
| Stuy Town/Peter Cooper Village | Manhattan | 5.344 | 4.842 | 90,61 |
| Alphabet City | Manhattan | 7.110 | 6.433 | 90,48 |
| Union Sq | Manhattan | 92.363 | 83.546 | 90,45 |
| Midtown East | Manhattan | 113.840 | 102.890 | 90,38 |
| Midtown Center | Manhattan | 163.866 | 147.299 | 89,89 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 65,98 % de los viajes de enero 2025 pagó cbd_congestion_fee (2.192.727 de 3.323.437, siempre US$ 0,75). El porcentaje está diluido porque el peaje empezó el 5 de enero: del 1 al 4 (10,4 % de los viajes del mes) casi nadie lo pagó (0,12 %; esos cobros anticipados quedan marcados por la regla R10), y desde el 5 lo paga el 73,6 %. Las cinco zonas con mayor proporción (Stuy Town/Peter Cooper Village, Alphabet City, Union Sq, Midtown East y Midtown Center, alrededor del 90 %) están todas en Manhattan, dentro de la zona de peaje. En enero 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 6.954 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 1 | 0 | Flex Fare | 412.946 | 2,74 | 3,02 |
| 2025 | 1 | 1 | Credit card | 2.423.279 | 26,29 | 22,94 |
| 2025 | 1 | 2 | Cash | 367.786 | 0,00 | 0,00 |
| 2025 | 1 | 3 | No charge | 12.025 | 0,01 | 0,02 |
| 2025 | 1 | 4 | Dispute | 35.497 | 0,03 | 0,02 |
| 2024 | 1 | 0 | Flex Fare | 115.127 | 9,14 | 9,06 |
| 2024 | 1 | 1 | Credit card | 2.297.767 | 26,26 | 22,62 |
| 2024 | 1 | 2 | Cash | 422.562 | 0,00 | 0,00 |
| 2024 | 1 | 3 | No charge | 10.383 | 0,04 | 0,03 |
| 2024 | 1 | 4 | Dispute | 22.680 | 0,03 | 0,02 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 26,29 % de la tarifa en 2025 frente a 26,26 % en 2024 (22,9 % y 22,6 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 4,1 % al 14,6 % de los viajes (115.127 → 412.946 con tarifa > 0) y cuya propina cae del 9,14 % al 2,74 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 5,8 % al 16,3 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 80,0 % al 72,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 1 | 270.966 | 58,03 | 157.420 | 116.346 |
| 2024 | 1 | 276.027 | 55,04 | 162.026 | 117.140 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 1,8 % (276.027 → 270.966) mientras el total de la ciudad sube un 15,8 %, así que su peso cae del 9,6 % al 8,2 % de los viajes. Por aeropuerto, JFK cae −2,8 % y LaGuardia cae −0,7 %. La tarifa promedio sube de US$ 55,04 a US$ 58,03 (+5,4 %), pero esa suba no es real: la produce un solo viaje de 2025 con fare_amount = US$ 863.372,12 (de LaGuardia Airport a Astoria Park, 1,6 millas, pago Dispute). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 55,01 a US$ 54,82 (−0,3 %), y la mediana baja de US$ 53,53 a US$ 52,70. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.323.437 | 2.870.896 | 452.541 | 15,76 | 17,73 | 18,47 | -4,00 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Enero 2025 tuvo 3.323.437 viajes válidos contra 2.870.896 en enero 2024: +452.541 viajes (+15,76 %). La recaudación total (total_amount) crece un 12,7 %, de US$ 78,4 M a US$ 88,3 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Parte del salto es de calendario: enero 2025 tuvo 5 jueves y 5 viernes (días fuertes), y enero 2024, 5 lunes y 5 martes (días flojos). Con el calendario de 2024 la variación sería +14,7 %. Todos los días de la semana crecen (por día), entre +11 % y +21 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 4,00 % (de US$ 18,47 a US$ 17,73); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 863.372) la baja es del 5,4 % (de US$ 18,46 a US$ 17,47). La mediana no cambia (US$ 12,80): no bajaron las tarifas, cambió la mezcla de viajes.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de enero 2025 hay más viajes Flex Fare, que son más baratos (US$ 14,84 contra US$ 17,91 del resto) y pasan del 4 % al 15 % de los viajes, menos viajes a aeropuertos (del 9,6 % al 8,2 %) y menos viajes de más de 10 millas (del 7,8 % al 6,8 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,6 % (de US$ 18,40 a US$ 17,91). El viaje promedio es más corto: 3,16 contra 3,29 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 3,16 % al 4,37 % de las filas leídas (151.789 filas en enero 2025 y 93.728 en enero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 2,04 %) y R04 (total cobrado faltante o negativo: 1,81 % contra 1,20 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en enero 2025 (+15,8 % de viajes, +12,7 % de recaudación). Las zonas que más suman viajes son Midtown Center (+16,9 %), Upper East Side South (+13,7 %) y Union Sq (+24,1 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 66,0 % de los viajes de enero 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Stuy Town/Peter Cooper Village +56,3 %, Alphabet City +117,2 % y Union Sq +24,1 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más corto (3,16 contra 3,29 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 12,80, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta no se mueve (26,3 % → 26,3 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Los promedios son frágiles: 40 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 863.372,12, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (enero 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,37 % y del 3,16 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-01 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-01`](http://localhost:8090/superset/dashboard/respaldo-local-2025-01/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 330 números en este reporte, 330 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:59 UTC, corrida `20261124T025852Z-98bd98`).

- Tablero `respaldo-local-2025-01`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.798 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 330 de 330 se ven en los charts que cita su bloque.
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
| Resumen | 3.323.437 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +15,8 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 2.870.896 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 88,3 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +12,7 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.475.226 | EC.1 | `filas_archivo` · 2025-01 (y 1 más) |
| Calidad | 3.475.226 | EC.1 | `filas_archivo` · 2025-01 (y 1 más) |
| Calidad | 3.323.437 | EC.1 | `aceptadas` · 2025-01 |
| Calidad | 151.789 | EC.1 | `cuarentena` · 2025-01 |
| Calidad | 4,37 | EC.1 | `pct_cuarentena` · 2025-01 |
| Calidad | 511.679 | EC.1 | `con_advertencias` · 2025-01 |
| Calidad | 14,72 | EC.1 | `pct_advertencias` · 2025-01 |
| Calidad | 2.964.624 | EC.1 | `filas_archivo` · 2024-01 (y 1 más) |
| Calidad | 2.964.624 | EC.1 | `filas_archivo` · 2024-01 (y 1 más) |
| Calidad | 2.870.896 | EC.1 | `aceptadas` · 2024-01 |
| Calidad | 93.728 | EC.1 | `cuarentena` · 2024-01 |
| Calidad | 3,16 | EC.1 | `pct_cuarentena` · 2024-01 |
| Calidad | 150.746 | EC.1 | `con_advertencias` · 2024-01 |
| Calidad | 5,08 | EC.1 | `pct_advertencias` · 2024-01 |
| Calidad | 22 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 18 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 2.051 | EC.2 | `filas_mes` · R02 |
| Calidad | 0,06 | EC.2 | `pct_mes` · R02 |
| Calidad | 870 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 91.055 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,62 | EC.2 | `pct_mes` · R03 |
| Calidad | 60.430 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,04 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,58 | EC.2 | `cambio_pp` · R03 |
| Calidad | 63.037 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,81 | EC.2 | `pct_mes` · R04 |
| Calidad | 35.504 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,20 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,62 | EC.2 | `cambio_pp` · R04 |
| Calidad | 564.805 | EC.2 | `filas_mes` · R05 |
| Calidad | 16,25 | EC.2 | `pct_mes` · R05 |
| Calidad | 171.627 | EC.2 | `filas_anterior` · R05 |
| Calidad | 5,79 | EC.2 | `pct_anterior` · R05 |
| Calidad | +10,46 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 148.413 | EC.2 | `filas_mes` · R08 |
| Calidad | 4,27 | EC.2 | `pct_mes` · R08 |
| Calidad | 41.402 | EC.2 | `filas_anterior` · R08 |
| Calidad | 1,40 | EC.2 | `pct_anterior` · R08 |
| Calidad | +2,87 | EC.2 | `cambio_pp` · R08 |
| Calidad | 982 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.107 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,04 | EC.2 | `pct_anterior` · R09 |
| Calidad | −0,01 | EC.2 | `cambio_pp` · R09 |
| Calidad | 6.954 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,20 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | +0,20 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 3,16 | EC.1 | `pct_cuarentena` · 2024-01 |
| Calidad | 4,37 | EC.1 | `pct_cuarentena` · 2025-01 |
| Calidad | 151.789 | EC.1 | `cuarentena` · 2025-01 |
| Calidad | 93.728 | EC.1 | `cuarentena` · 2024-01 |
| Calidad | 2,62 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,04 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,81 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,20 | EC.2 | `pct_anterior` · R04 |
| Calidad | 511.679 | EC.1 | `con_advertencias` · 2025-01 |
| Calidad | 14,7 | EC.1 | `pct_advertencias` · 2025-01 |
| Calidad | 16,3 | EC.2 | `pct_mes` · R05 |
| Calidad | 5,8 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 163.866 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 140.220 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 23.646 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 16,86 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 159.330 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 140.160 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 19.170 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 13,68 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 151.616 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 134.027 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 17.589 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 13,12 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 134.804 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 138.341 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -3.537 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -2,56 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 120.657 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 102.999 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 17.658 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 17,14 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 115.021 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 102.165 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 12.856 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 12,58 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 113.840 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 104.374 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 9.466 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 9,07 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 107.540 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 101.847 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 5.693 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 5,59 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 93.831 | E1.1 | `viajes_mes` · Upper West Side South Manhattan |
| Pregunta 1 | 86.532 | E1.1 | `viajes_anterior` · Upper West Side South Manhattan |
| Pregunta 1 | 7.299 | E1.1 | `variacion` · Upper West Side South Manhattan |
| Pregunta 1 | 8,44 | E1.1 | `variacion_pct` · Upper West Side South Manhattan |
| Pregunta 1 | 92.702 | E1.1 | `viajes_mes` · Midtown North Manhattan |
| Pregunta 1 | 83.711 | E1.1 | `viajes_anterior` · Midtown North Manhattan |
| Pregunta 1 | 8.991 | E1.1 | `variacion` · Midtown North Manhattan |
| Pregunta 1 | 10,74 | E1.1 | `variacion_pct` · Midtown North Manhattan |
| Pregunta 1 | +5,6 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan (y 2 más) |
| Pregunta 1 | +17,1 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan (y 1 más) |
| Pregunta 1 | −2,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 163.866 | E1.1 | `viajes_mes` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | +16,9 | E1.1 | `variacion_pct` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | 4 | E1.1 | `puesto_anterior` · Upper East Side North Manhattan (y 4 más) |
| Pregunta 1 | −2,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −1,4 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | 37,7 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 39,7 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 22.286 | E1.6 | `viajes_anterior` · Brooklyn |
| Pregunta 1 | 60.244 | E1.6 | `viajes_mes` · Brooklyn |
| Pregunta 1 | +15,8 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 2:00 (y 4 más) |
| Pregunta 2 | 21.233 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 33,64 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 2:00 (y 4 más) |
| Pregunta 2 | 17.490 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 37,54 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 2:00 (y 14 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 10:00 (y 6 más) |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 2:00 (y 14 más) |
| Pregunta 2 | 12:00 | E2.1 | `hora` · 12:00 (y 5 más) |
| Pregunta 2 | 33,64 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 37,54 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 21.233 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 242.182 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 20,8 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,2 | E2.1 | `variacion_ingreso_pct` · 4:00 (y 1 más) |
| Pregunta 2 | 5,71 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,16 | E2.5 | `valor_mes` · Distancia media (y 2 más) |
| Pregunta 2 | 25,8 | E2.1 | `ingreso_viaje_anterior` · 1:00 (y 3 más) |
| Pregunta 2 | 20,8 | E2.6 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 6,23 | E2.6 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 5,71 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 10,4 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 2 más) |
| Pregunta 2 | 30,68 | E2.1 | `ingreso_viaje_mes` · 12:00 (y 1 más) |
| Pregunta 2 | 863.372,12 | E2.7 | `tarifa_maxima_mes` · 12:00 |
| Pregunta 2 | 25,59 | E2.7 | `ingreso_sin_atipicas_mes` · 12:00 |
| Pregunta 3 | 3.323.437 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.192.727 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 65,98 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 5.344 | E3.3 | `viajes` · Stuy Town/Peter Cooper Village Manhattan |
| Pregunta 3 | 4.842 | E3.3 | `viajes_con_peaje` · Stuy Town/Peter Cooper Village Manhattan |
| Pregunta 3 | 90,61 | E3.3 | `pct_con_peaje` · Stuy Town/Peter Cooper Village Manhattan |
| Pregunta 3 | 7.110 | E3.3 | `viajes` · Alphabet City Manhattan |
| Pregunta 3 | 6.433 | E3.3 | `viajes_con_peaje` · Alphabet City Manhattan |
| Pregunta 3 | 90,48 | E3.3 | `pct_con_peaje` · Alphabet City Manhattan |
| Pregunta 3 | 92.363 | E3.3 | `viajes` · Union Sq Manhattan |
| Pregunta 3 | 83.546 | E3.3 | `viajes_con_peaje` · Union Sq Manhattan |
| Pregunta 3 | 90,45 | E3.3 | `pct_con_peaje` · Union Sq Manhattan |
| Pregunta 3 | 113.840 | E3.3 | `viajes` · Midtown East Manhattan |
| Pregunta 3 | 102.890 | E3.3 | `viajes_con_peaje` · Midtown East Manhattan |
| Pregunta 3 | 90,38 | E3.3 | `pct_con_peaje` · Midtown East Manhattan |
| Pregunta 3 | 163.866 | E3.3 | `viajes` · Midtown Center Manhattan |
| Pregunta 3 | 147.299 | E3.3 | `viajes_con_peaje` · Midtown Center Manhattan |
| Pregunta 3 | 89,89 | E3.3 | `pct_con_peaje` · Midtown Center Manhattan |
| Pregunta 3 | 65,98 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.192.727 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.323.437 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 10,4 | E3.1 | `valor_mes` · Viajes del mes anteriores al inicio del peaje (2025-01-05) |
| Pregunta 3 | 0,12 | E3.1 | `valor_mes` · Viajes con peaje antes del inicio (2025-01-05) |
| Pregunta 3 | 73,6 | E3.1 | `valor_mes` · Viajes con peaje desde el inicio (2025-01-05) |
| Pregunta 3 | 90 | E3.3 | `pct_con_peaje` · Alphabet City Manhattan (y 3 más) |
| Pregunta 3 | 6.954 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 412.946 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,74 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 3,02 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.423.279 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 26,29 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,94 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash (y 1 más) |
| Pregunta 4 | 367.786 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 6 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 6 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 12.025 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_mes` · No charge (y 1 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_mes` · No charge (y 2 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 35.497 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_mes` · No charge (y 2 más) |
| Pregunta 4 | 115.127 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 9,14 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 9,06 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.297.767 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 26,26 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,62 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash (y 1 más) |
| Pregunta 4 | 422.562 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 6 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 6 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 10.383 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,04 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 22.680 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_mes` · No charge (y 2 más) |
| Pregunta 4 | 26,29 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 26,26 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,9 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,6 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 94 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 4,1 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 14,6 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 115.127 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 412.946 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 9,14 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,74 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 5,8 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 16,3 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 80,0 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 72,9 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 270.966 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 58,03 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 157.420 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 116.346 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 276.027 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,04 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 162.026 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 117.140 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 1,8 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 276.027 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 270.966 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 15,8 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,6 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,2 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −2,8 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −0,7 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 55,04 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 58,03 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | +5,4 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 863.372,12 | E5.1 | `valor_mes` · Tarifa máxima de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 1,6 | E5.1 | `variacion_pct` · Tarifa mediana de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 55,01 | E5.1 | `valor_anterior` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 54,82 | E5.1 | `valor_mes` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | −0,3 | E5.1 | `variacion_pct` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 53,53 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 52,70 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.323.437 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 2.870.896 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 452.541 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 15,76 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 17,73 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 18,47 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | -4,00 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.323.437 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 2.870.896 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +452.541 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +15,76 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 12,7 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 78,4 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 88,3 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 6 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 6 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 6 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 6 más) |
| Pregunta 6 | +14,7 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | +11 | E6.2 | `variacion_por_dia_pct` · lunes |
| Pregunta 6 | +21 | E6.2 | `variacion_por_dia_pct` · martes |
| Pregunta 6 | 4,00 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 18,47 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 17,73 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 863.372 | E6.1 | `valor_mes` · Tarifa máxima (y 1 más) |
| Pregunta 6 | 5,4 | E6.1 | `variacion_pct` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 18,46 | E6.1 | `valor_anterior` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 17,47 | E6.1 | `valor_mes` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 12,80 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 14,84 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 17,91 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 4 | E6.5 | `variacion_pct` · Distancia media (y 2 más) |
| Pregunta 6 | 15 | E6.5 | `valor_mes` · Duración media (y 4 más) |
| Pregunta 6 | 9,6 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,2 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,8 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 6,8 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 2,6 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 18,40 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 17,91 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,16 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,29 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 3,16 | EC.1 | `pct_cuarentena` · 2024-01 |
| Pregunta 6 | 4,37 | EC.1 | `pct_cuarentena` · 2025-01 |
| Pregunta 6 | 151.789 | EC.1 | `cuarentena` · 2025-01 |
| Pregunta 6 | 93.728 | EC.1 | `cuarentena` · 2024-01 |
| Pregunta 6 | 2,62 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,04 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,81 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,20 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +15,8 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +12,7 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +16,9 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | +13,7 | C1.2 | `variacion_pct` · Upper East Side South Manhattan |
| Conclusiones | +24,1 | C1.2 | `variacion_pct` · Union Sq Manhattan |
| Conclusiones | 66,0 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +56,3 | C2.2 | `variacion_viajes_pct` · Stuy Town/Peter Cooper Village Manhattan |
| Conclusiones | +117,2 | C2.2 | `variacion_viajes_pct` · Alphabet City Manhattan |
| Conclusiones | +24,1 | C2.2 | `variacion_viajes_pct` · Union Sq Manhattan |
| Conclusiones | 3,16 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,29 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 12,80 | C3.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Conclusiones | 26,3 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito (y 1 más) |
| Conclusiones | 26,3 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito (y 1 más) |
| Conclusiones | 40 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 863.372,12 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,37 | C5.1 | `pct_cuarentena` · 2025-01 |
| Conclusiones | 3,16 | C5.1 | `pct_cuarentena` · 2024-01 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-01/#CHART-C5-2
