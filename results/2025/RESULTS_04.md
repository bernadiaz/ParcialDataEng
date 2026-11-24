# Resultados: abril 2025 vs abril 2024

> En abril 2025 los taxis amarillos hicieron 3.776.409 viajes válidos, +10,2 % que en abril 2024 (3.427.499), con una recaudación de US$ 104,2 M (+8,3 %).

**Respaldo en Superset:** [E0.1 Viajes válidos][E0.1] · [E0.2 Viajes, año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación (USD)][E0.4] · [E0.6 Recaudación, cambio (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-04 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-04.parquet` y `yellow_tripdata_2024-04.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-04`](http://localhost:8090/superset/dashboard/respaldo-local-2025-04/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T025639Z-7e1080`, 2026-11-24 02:56 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=04/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-04 | `yellow_tripdata_2025-04.parquet` | 3.970.553 | 3.970.553 | 3.776.409 | 194.144 | 4,89 % | 721.657 (18,18 %) | sí |
| 2024-04 | `yellow_tripdata_2024-04.parquet` | 3.514.289 | 3.514.289 | 3.427.499 | 86.790 | 2,47 % | 443.403 (12,62 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-04 | 2024-04 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 9 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 34.769 (0,88 %) | 1.089 (0,03 %) | +0,84 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 91.745 (2,31 %) | 45.963 (1,31 %) | +1,00 pp |
| R04 | reject | Total cobrado faltante o negativo. | 72.608 (1,83 %) | 43.749 (1,24 %) | +0,58 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 768.831 (19,36 %) | 448.167 (12,75 %) | +6,61 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 191.095 (4,81 %) | 61.715 (1,76 %) | +3,06 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.095 (0,03 %) | 1.141 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 50.646 (1,28 %) | 0 (0,00 %) | +1,28 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 2,47 % al 4,89 % de las filas leídas (194.144 filas en abril 2025 y 86.790 en abril 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,31 % contra 1,31 %) y R04 (total cobrado faltante o negativo: 1,83 % contra 1,24 %).
- Las reglas de advertencia no sacan filas: 721.657 filas aceptadas de abril 2025 (18,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 19,4 %, contra 12,8 % en abril 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de abril 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de abril 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 178.609 | 162.264 | 16.345 | 10,07 |
| Manhattan | Midtown Center | 175.894 | 160.322 | 15.572 | 9,71 |
| Manhattan | Upper East Side North | 156.358 | 149.735 | 6.623 | 4,42 |
| Queens | JFK Airport | 145.700 | 148.949 | -3.249 | -2,18 |
| Manhattan | Times Sq/Theatre District | 127.528 | 113.886 | 13.642 | 11,98 |
| Manhattan | Penn Station/Madison Sq West | 121.862 | 109.149 | 12.713 | 11,65 |
| Manhattan | Midtown East | 119.413 | 116.920 | 2.493 | 2,13 |
| Manhattan | Lincoln Square East | 111.862 | 114.914 | -3.052 | -2,66 |
| Queens | LaGuardia Airport | 104.118 | 108.954 | -4.836 | -4,44 |
| Manhattan | Union Sq | 102.737 | 91.314 | 11.423 | 12,51 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, siete crecen (entre +2,1 % en Midtown East y +12,5 % en Union Sq) y tres caen (LaGuardia Airport −4,4 %, Lincoln Square East −2,7 %, JFK Airport −2,2 %). Upper East Side South lidera con 178.609 viajes (+10,1 %). Respecto de abril 2024 entra al top 10 Union Sq y sale Upper West Side South. En los aeropuertos, JFK (puesto 4 del top) cae −2,2 % y LaGuardia (puesto 9 del top) cae −4,4 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 35,6 % de los pickups, frente al 37,5 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (10.002 → 28.212), aunque sobre una base chica, contra +10,2 % del total.

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
| 2025 | 4 | 5 | 28.320 | 32,73 |
| 2024 | 4 | 5 | 21.677 | 35,11 |

**Respaldo en Superset:** [E2.1 Las 24 horas: viajes e ingreso promedio por viaje][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 32,73 en 2025 y US$ 35,11 en 2024. Es una hora de poco volumen (28.320 viajes, contra 253.620 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,0 % de sus viajes toca JFK o LaGuardia (contra 8,3 % en todo el mes) y la distancia media es de 5,75 millas (contra 3,37). En 2025 los viajes de aeropuerto son menos (del 22,1 % al 18,0 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 6,8 %.

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
| ALL ZONES |  | 3.776.409 | 2.792.607 | 73,95 |
| Battery Park | Manhattan | 1.458 | 1.456 | 99,86 |
| SoHo | Manhattan | 32.366 | 32.314 | 99,84 |
| Greenwich Village South | Manhattan | 55.765 | 55.671 | 99,83 |
| West Village | Manhattan | 85.049 | 84.862 | 99,78 |
| Greenwich Village North | Manhattan | 54.991 | 54.868 | 99,78 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 73,95 % de los viajes de abril 2025 pagó cbd_congestion_fee (2.792.607 de 3.776.409, siempre US$ 0,75). Las cinco zonas con mayor proporción (Battery Park, SoHo, Greenwich Village South, West Village y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En abril 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 50.646 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 4 | 0 | Flex Fare | 591.396 | 2,04 | 2,10 |
| 2025 | 4 | 1 | Credit card | 2.635.152 | 25,94 | 22,58 |
| 2025 | 4 | 2 | Cash | 382.522 | 0,00 | 0,00 |
| 2025 | 4 | 3 | No charge | 14.509 | 0,02 | 0,01 |
| 2025 | 4 | 4 | Dispute | 47.550 | 0,05 | 0,04 |
| 2024 | 4 | 0 | Flex Fare | 388.204 | 3,05 | 3,27 |
| 2024 | 4 | 1 | Credit card | 2.535.054 | 25,46 | 22,32 |
| 2024 | 4 | 2 | Cash | 450.227 | 0,00 | 0,00 |
| 2024 | 4 | 3 | No charge | 11.853 | 0,01 | 0,01 |
| 2024 | 4 | 4 | Dispute | 27.617 | 0,05 | 0,08 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.5 Viajes con tarifa mayor a cero y cuántos dejan propina][E4.5]

**Interpretación:** Con tarjeta de crédito la propina sube: 25,94 % de la tarifa en 2025 frente a 25,46 % en 2024 (22,6 % y 22,3 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,7 % al 18,4 % de los viajes (388.204 → 591.396 con tarifa > 0) y cuya propina cae del 3,05 % al 2,04 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 12,8 % al 19,4 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,0 % al 69,8 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 4 | 314.242 | 55,78 | 175.743 | 141.112 |
| 2024 | 4 | 322.668 | 55,58 | 179.893 | 145.789 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 2,6 % (322.668 → 314.242) mientras el total de la ciudad sube un 10,2 %, así que su peso cae del 9,4 % al 8,3 % de los viajes. Por aeropuerto, JFK cae −2,3 % y LaGuardia cae −3,2 %. La tarifa promedio se mantiene (US$ 55,58 → US$ 55,78), y la mediana se mantiene en US$ 54,80. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.776.409 | 3.427.499 | 348.910 | 10,18 | 18,65 | 19,36 | -3,65 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Abril 2025 tuvo 3.776.409 viajes válidos contra 3.427.499 en abril 2024: +348.910 viajes (+10,18 %). La recaudación total (total_amount) crece un 8,3 %, de US$ 96,2 M a US$ 104,2 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Parte del salto es de calendario: abril 2025 tuvo 5 miércoles, y abril 2024, 5 lunes (días flojos). Con el calendario de 2024 la variación sería +9,4 %. Todos los días de la semana crecen (por día), entre +3 % y +15 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 3,65 % (de US$ 19,36 a US$ 18,65). La mediana no cambia (US$ 13,50): no bajaron las tarifas, cambió la mezcla de viajes.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de abril 2025 hay más viajes Flex Fare, que son más baratos (US$ 16,98 contra US$ 19,03 del resto) y pasan del 12 % al 18 % de los viajes, menos viajes a aeropuertos (del 9,4 % al 8,3 %) y menos viajes de más de 10 millas (del 7,8 % al 7,3 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,0 % (de US$ 19,41 a US$ 19,03).
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 2,47 % al 4,89 % de las filas leídas (194.144 filas en abril 2025 y 86.790 en abril 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,31 % contra 1,31 %) y R04 (total cobrado faltante o negativo: 1,83 % contra 1,24 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en abril 2025 (+10,2 % de viajes, +8,3 % de recaudación). Las zonas que más suman viajes son Upper East Side South (+10,1 %), Midtown Center (+9,7 %) y Times Sq/Theatre District (+12,0 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 73,9 % de los viajes de abril 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Battery Park +9,8 %, SoHo +23,0 % y Greenwich Village South +16,7 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es igual de largo (3,37 contra 3,39 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 13,50, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta sube (25,5 % → 25,9 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 32 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 870,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.7 Las 24 horas: ingreso por viaje sin tarifas atípicas y tarifa máxima][E2.7]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (abril 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,89 % y del 2,47 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-04 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-04`](http://localhost:8090/superset/dashboard/respaldo-local-2025-04/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 309 números en este reporte, 309 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 03:01 UTC, corrida `20261124T025852Z-98bd98`).

- Tablero `respaldo-local-2025-04`: 58 de 58 charts devolvieron por la API exactamente los datos de este reporte (4.780 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
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
| Resumen | 3.776.409 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +10,2 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.427.499 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 104,2 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +8,3 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.970.553 | EC.1 | `filas_archivo` · 2025-04 (y 1 más) |
| Calidad | 3.970.553 | EC.1 | `filas_archivo` · 2025-04 (y 1 más) |
| Calidad | 3.776.409 | EC.1 | `aceptadas` · 2025-04 |
| Calidad | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Calidad | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Calidad | 721.657 | EC.1 | `con_advertencias` · 2025-04 |
| Calidad | 18,18 | EC.1 | `pct_advertencias` · 2025-04 |
| Calidad | 3.514.289 | EC.1 | `filas_archivo` · 2024-04 (y 1 más) |
| Calidad | 3.514.289 | EC.1 | `filas_archivo` · 2024-04 (y 1 más) |
| Calidad | 3.427.499 | EC.1 | `aceptadas` · 2024-04 |
| Calidad | 86.790 | EC.1 | `cuarentena` · 2024-04 |
| Calidad | 2,47 | EC.1 | `pct_cuarentena` · 2024-04 |
| Calidad | 443.403 | EC.1 | `con_advertencias` · 2024-04 |
| Calidad | 12,62 | EC.1 | `pct_advertencias` · 2024-04 |
| Calidad | 7 | EC.2 | `filas_mes` · R01 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 9 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 34.769 | EC.2 | `filas_mes` · R02 |
| Calidad | 0,88 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.089 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +0,84 | EC.2 | `cambio_pp` · R02 |
| Calidad | 91.745 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,31 | EC.2 | `pct_mes` · R03 |
| Calidad | 45.963 | EC.2 | `filas_anterior` · R03 |
| Calidad | 1,31 | EC.2 | `pct_anterior` · R03 |
| Calidad | +1,00 | EC.2 | `cambio_pp` · R03 |
| Calidad | 72.608 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,83 | EC.2 | `pct_mes` · R04 |
| Calidad | 43.749 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,24 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,58 | EC.2 | `cambio_pp` · R04 |
| Calidad | 768.831 | EC.2 | `filas_mes` · R05 |
| Calidad | 19,36 | EC.2 | `pct_mes` · R05 |
| Calidad | 448.167 | EC.2 | `filas_anterior` · R05 |
| Calidad | 12,75 | EC.2 | `pct_anterior` · R05 |
| Calidad | +6,61 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 191.095 | EC.2 | `filas_mes` · R08 |
| Calidad | 4,81 | EC.2 | `pct_mes` · R08 |
| Calidad | 61.715 | EC.2 | `filas_anterior` · R08 |
| Calidad | 1,76 | EC.2 | `pct_anterior` · R08 |
| Calidad | +3,06 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.095 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.141 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 50.646 | EC.2 | `filas_mes` · R10 |
| Calidad | 1,28 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | +1,28 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 2,47 | EC.1 | `pct_cuarentena` · 2024-04 |
| Calidad | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Calidad | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Calidad | 86.790 | EC.1 | `cuarentena` · 2024-04 |
| Calidad | 2,31 | EC.2 | `pct_mes` · R03 |
| Calidad | 1,31 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,83 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,24 | EC.2 | `pct_anterior` · R04 |
| Calidad | 721.657 | EC.1 | `con_advertencias` · 2025-04 |
| Calidad | 18,2 | EC.1 | `pct_advertencias` · 2025-04 |
| Calidad | 19,4 | EC.2 | `pct_mes` · R05 |
| Calidad | 12,8 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 178.609 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 162.264 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 16.345 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 10,07 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 175.894 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 160.322 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 15.572 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 9,71 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 156.358 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 149.735 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 6.623 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 4,42 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 145.700 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 148.949 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -3.249 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -2,18 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 127.528 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 113.886 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 13.642 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 11,98 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 121.862 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 109.149 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 12.713 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 11,65 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 119.413 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 116.920 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 2.493 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 2,13 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 111.862 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 114.914 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -3.052 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -2,66 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 104.118 | E1.1 | `viajes_mes` · LaGuardia Airport Queens |
| Pregunta 1 | 108.954 | E1.1 | `viajes_anterior` · LaGuardia Airport Queens |
| Pregunta 1 | -4.836 | E1.1 | `variacion` · LaGuardia Airport Queens |
| Pregunta 1 | -4,44 | E1.1 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | 102.737 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 91.314 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | 11.423 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | 12,51 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | +2,1 | E1.1 | `variacion_pct` · Midtown East Manhattan (y 1 más) |
| Pregunta 1 | +12,5 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | −4,4 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | −2,7 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan (y 1 más) |
| Pregunta 1 | −2,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 178.609 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +10,1 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 4 | E1.1 | `variacion_pct` · Upper East Side North Manhattan (y 10 más) |
| Pregunta 1 | −2,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 9 | E1.1 | `puesto_mes` · LaGuardia Airport Queens (y 7 más) |
| Pregunta 1 | −4,4 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | 35,6 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 37,5 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 10.002 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 28.212 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +10,2 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 2 más) |
| Pregunta 2 | 28.320 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 32,73 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `hora` · 5:00 (y 2 más) |
| Pregunta 2 | 21.677 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 35,11 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 12 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 10:00 (y 7 más) |
| Pregunta 2 | 5:00 | E2.1 | `hora` · 5:00 (y 12 más) |
| Pregunta 2 | 32,73 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 3 más) |
| Pregunta 2 | 35,11 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 3 más) |
| Pregunta 2 | 28.320 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 253.620 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 18,0 | E2.1 | `puesto_mes` · 10:00 (y 7 más) |
| Pregunta 2 | 8,3 | E2.5 | `valor_mes` · Participación de los viajes de aeropuerto (y 1 más) |
| Pregunta 2 | 5,75 | E2.6 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,37 | E2.5 | `valor_mes` · Distancia media (y 2 más) |
| Pregunta 2 | 22,1 | E2.6 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 18,0 | E2.1 | `puesto_mes` · 10:00 (y 7 más) |
| Pregunta 2 | 6,8 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 1 más) |
| Pregunta 3 | 3.776.409 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.792.607 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 73,95 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 1.458 | E3.3 | `viajes` · Battery Park Manhattan |
| Pregunta 3 | 1.456 | E3.3 | `viajes_con_peaje` · Battery Park Manhattan |
| Pregunta 3 | 99,86 | E3.3 | `pct_con_peaje` · Battery Park Manhattan |
| Pregunta 3 | 32.366 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 32.314 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,84 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 55.765 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 55.671 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,83 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 85.049 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 84.862 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,78 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 1 más) |
| Pregunta 3 | 54.991 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 54.868 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,78 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 1 más) |
| Pregunta 3 | 73,95 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.792.607 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.776.409 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · Battery Park Manhattan (y 4 más) |
| Pregunta 3 | 50.646 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 591.396 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 2,04 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 2,10 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.635.152 | E4.5 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 25,94 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,58 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 382.522 | E4.5 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 3 más) |
| Pregunta 4 | 14.509 | E4.5 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_anterior` · No charge (y 4 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 47.550 | E4.5 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_mes` · Dispute (y 1 más) |
| Pregunta 4 | 0,04 | E4.1 | `propina_ponderada_pct_mes` · Dispute (y 1 más) |
| Pregunta 4 | 388.204 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 3,05 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 3,27 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 1 más) |
| Pregunta 4 | 2.535.054 | E4.5 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,46 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,32 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 3 más) |
| Pregunta 4 | 450.227 | E4.5 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 3 más) |
| Pregunta 4 | 11.853 | E4.5 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_anterior` · No charge (y 4 más) |
| Pregunta 4 | 0,01 | E4.1 | `propina_media_pct_anterior` · No charge (y 4 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute (y 1 más) |
| Pregunta 4 | 27.617 | E4.5 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_mes` · Dispute (y 1 más) |
| Pregunta 4 | 0,08 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 25,94 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,46 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,6 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,3 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 94 | E4.5 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 11,7 | E4.6 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 18,4 | E4.6 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 388.204 | E4.5 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 591.396 | E4.5 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 3,05 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 2,04 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 12,8 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 19,4 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 74,0 | E4.6 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 69,8 | E4.6 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 314.242 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,78 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 175.743 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 141.112 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 322.668 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,58 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 179.893 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 145.789 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 2,6 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 322.668 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 314.242 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 10,2 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,4 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,3 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −2,3 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −3,2 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 55,58 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,78 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 54,80 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.776.409 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.427.499 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 348.910 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 10,18 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 18,65 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,36 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | -3,65 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 3.776.409 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.427.499 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +348.910 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +10,18 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 8,3 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 96,2 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 104,2 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 3 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · lunes (y 3 más) |
| Pregunta 6 | +9,4 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | +3 | E6.2 | `variacion_por_dia_pct` · jueves |
| Pregunta 6 | +15 | E6.2 | `variacion_por_dia_pct` · sábado (y 1 más) |
| Pregunta 6 | 3,65 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,36 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 18,65 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 13,50 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 16,98 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 19,03 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 12 | E6.5 | `valor_anterior` · Participación de Flex Fare (y 1 más) |
| Pregunta 6 | 18 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 9,4 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,3 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,8 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 7,3 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 2,0 | E6.5 | `variacion` · Tarifa media Flex Fare (y 3 más) |
| Pregunta 6 | 19,41 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 19,03 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 2,47 | EC.1 | `pct_cuarentena` · 2024-04 |
| Pregunta 6 | 4,89 | EC.1 | `pct_cuarentena` · 2025-04 |
| Pregunta 6 | 194.144 | EC.1 | `cuarentena` · 2025-04 |
| Pregunta 6 | 86.790 | EC.1 | `cuarentena` · 2024-04 |
| Pregunta 6 | 2,31 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 1,31 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,83 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,24 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +10,2 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +8,3 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +10,1 | C1.2 | `variacion_pct` · Upper East Side South Manhattan |
| Conclusiones | +9,7 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | +12,0 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | 73,9 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +9,8 | C2.2 | `variacion_viajes_pct` · Battery Park Manhattan |
| Conclusiones | +23,0 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan |
| Conclusiones | +16,7 | C2.2 | `variacion_viajes_pct` · Greenwich Village South Manhattan |
| Conclusiones | 3,37 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,39 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 13,50 | C3.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Conclusiones | 25,5 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 25,9 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 32 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 870,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,89 | C5.1 | `pct_cuarentena` · 2025-04 |
| Conclusiones | 2,47 | C5.1 | `pct_cuarentena` · 2024-04 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-5
[E2.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-6
[E2.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E2-7
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-1
[E4.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-5
[E4.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-6
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-04/#CHART-C5-2
