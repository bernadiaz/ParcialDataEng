# Resultados: octubre 2025 vs octubre 2024

> En octubre 2025 los taxis amarillos hicieron 4.135.934 viajes válidos, +12,0 % que en octubre 2024 (3.694.253), con una recaudación de US$ 116,6 M (+7,8 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-10 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-10.parquet` y `yellow_tripdata_2024-10.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-10`](http://localhost:8090/superset/dashboard/respaldo-local-2025-10/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T015201Z-299545`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=10/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-10 | `yellow_tripdata_2025-10.parquet` | 4.428.699 | 4.428.699 | 4.135.934 | 292.765 | 6,61 % | 900.005 (20,32 %) | sí |
| 2024-10 | `yellow_tripdata_2024-10.parquet` | 3.833.771 | 3.833.771 | 3.694.253 | 139.518 | 3,64 % | 395.875 (10,33 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-10 | 2024-10 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 13 (0,00 %) | 40 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 67.968 (1,53 %) | 1.002 (0,03 %) | +1,51 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 125.828 (2,84 %) | 81.768 (2,13 %) | +0,71 pp |
| R04 | reject | Total cobrado faltante o negativo. | 108.735 (2,46 %) | 61.426 (1,60 %) | +0,85 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.013.197 (22,88 %) | 429.665 (11,21 %) | +11,67 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 2 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 325.991 (7,36 %) | 79.878 (2,08 %) | +5,28 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.292 (0,03 %) | 1.107 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 45.667 (1,03 %) | 0 (0,00 %) | +1,03 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 3,64 % al 6,61 % de las filas leídas (292.765 filas en octubre 2025 y 139.518 en octubre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,84 % contra 2,13 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,60 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,51 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 900.005 filas aceptadas de octubre 2025 (20,3 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 22,9 %, contra 11,2 % en octubre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de octubre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de octubre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 194.841 | 186.500 | 8.341 | 4,47 |
| Manhattan | Midtown Center | 181.822 | 172.520 | 9.302 | 5,39 |
| Queens | JFK Airport | 175.520 | 181.887 | -6.367 | -3,50 |
| Manhattan | Upper East Side North | 170.014 | 163.408 | 6.606 | 4,04 |
| Manhattan | Midtown East | 130.474 | 128.423 | 2.051 | 1,60 |
| Manhattan | Penn Station/Madison Sq West | 128.125 | 117.838 | 10.287 | 8,73 |
| Manhattan | Lincoln Square East | 125.928 | 121.689 | 4.239 | 3,48 |
| Manhattan | Times Sq/Theatre District | 124.096 | 122.769 | 1.327 | 1,08 |
| Queens | LaGuardia Airport | 116.342 | 115.354 | 988 | 0,86 |
| Manhattan | Union Sq | 109.738 | 101.986 | 7.752 | 7,60 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +0,9 % en LaGuardia Airport y +8,7 % en Penn Station/Madison Sq West) y una cae (JFK Airport −3,5 %). Upper East Side South lidera con 194.841 viajes (+4,5 %). Respecto de octubre 2024 entra al top 10 Union Sq y sale Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −3,5 % y LaGuardia (puesto 9 del top) crece +0,9 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 35,2 % de los pickups, frente al 38,4 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (11.308 → 30.719), aunque sobre una base chica, contra +12,0 % del total.

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
| 2025 | 10 | 16 | 235.339 | 32,29 |
| 2024 | 10 | 5 | 24.200 | 37,10 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 16:00 en 2025 (US$ 32,29) y las 5:00 en 2024 (US$ 37,10). Además es una hora de mucho movimiento (235.339 viajes; la hora pico es las 18:00 con 276.793). No la explican los aeropuertos ni la distancia, que a esa hora son parecidos al resto del día: pesan los recargos y peajes de esos viajes.

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
| ALL ZONES |  | 4.135.934 | 3.053.045 | 73,82 |
| SoHo | Manhattan | 33.646 | 33.554 | 99,73 |
| Greenwich Village South | Manhattan | 60.111 | 59.943 | 99,72 |
| West Village | Manhattan | 89.093 | 88.820 | 99,69 |
| Midtown North | Manhattan | 109.198 | 108.795 | 99,63 |
| Greenwich Village North | Manhattan | 59.424 | 59.177 | 99,58 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 73,82 % de los viajes de octubre 2025 pagó cbd_congestion_fee (3.053.045 de 4.135.934, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Midtown North y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En octubre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 45.667 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 10 | 0 | Flex Fare | 682.354 | 1,77 | 2,11 |
| 2025 | 10 | 1 | Credit card | 2.834.834 | 24,91 | 21,47 |
| 2025 | 10 | 2 | Cash | 366.204 | 0,00 | 0,00 |
| 2025 | 10 | 3 | No charge | 13.497 | 0,02 | 0,02 |
| 2025 | 10 | 4 | Dispute | 45.833 | 0,02 | 0,02 |
| 2024 | 10 | 0 | Flex Fare | 345.123 | 3,27 | 3,60 |
| 2024 | 10 | 1 | Credit card | 2.828.683 | 24,73 | 21,97 |
| 2024 | 10 | 2 | Cash | 452.812 | 0,00 | 0,00 |
| 2024 | 10 | 3 | No charge | 14.609 | 0,03 | 0,02 |
| 2024 | 10 | 4 | Dispute | 39.375 | 0,03 | 0,03 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 24,91 % de la tarifa en 2025 frente a 24,73 % en 2024 (21,5 % y 22,0 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 9,7 % al 21,2 % de los viajes (345.123 → 682.354 con tarifa > 0) y cuya propina cae del 3,27 % al 1,77 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 11,2 % al 22,9 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 76,6 % al 68,5 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 10 | 358.652 | 57,04 | 205.167 | 156.460 |
| 2024 | 10 | 373.321 | 57,15 | 217.015 | 159.549 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 3,9 % (373.321 → 358.652) mientras el total de la ciudad sube un 12,0 %, así que su peso cae del 10,1 % al 8,7 % de los viajes. Por aeropuerto, JFK cae −5,5 % y LaGuardia cae −1,9 %. La tarifa promedio se mantiene (US$ 57,15 → US$ 57,04), y la mediana baja de US$ 59,00 a US$ 57,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 4.135.934 | 3.694.253 | 441.681 | 11,96 | 19,17 | 20,29 | -5,50 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Octubre 2025 tuvo 4.135.934 viajes válidos contra 3.694.253 en octubre 2024: +441.681 viajes (+11,96 %). La recaudación total (total_amount) crece un 7,8 %, de US$ 108,2 M a US$ 116,6 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- Parte del salto es de calendario: octubre 2025 tuvo 5 viernes (días fuertes), y octubre 2024, 5 martes (días flojos). Con el calendario de 2024 la variación sería +11,5 %. Todos los días de la semana crecen (por día), entre +7 % y +17 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 5,50 % (de US$ 20,29 a US$ 19,17). La mediana no cambia (US$ 14,20): no bajaron las tarifas, cambió la mezcla de viajes.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de octubre 2025 hay más viajes Flex Fare, que son más baratos (US$ 13,98 contra US$ 20,56 del resto) y pasan del 10 % al 21 % de los viajes, menos viajes a aeropuertos (del 10,1 % al 8,7 %) y menos viajes de más de 10 millas (del 8,5 % al 8,2 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,40 a US$ 20,56). El viaje promedio es más largo: 3,58 contra 3,48 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 3,64 % al 6,61 % de las filas leídas (292.765 filas en octubre 2025 y 139.518 en octubre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,84 % contra 2,13 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,60 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en octubre 2025 (+12,0 % de viajes, +7,8 % de recaudación). Las zonas que más suman viajes son East Village (+28,1 %), West Chelsea/Hudson Yards (+21,5 %) y Lower East Side (+33,7 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 73,8 % de los viajes de octubre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +9,3 %, Greenwich Village South +10,1 % y West Village +6,0 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,58 contra 3,48 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 14,20, así que el cambio viene de la mezcla de viajes (más Flex Fare y menos aeropuertos). La propina con tarjeta no se mueve (24,7 % → 24,9 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 40 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 800,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (octubre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,61 % y del 3,64 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-10 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-10`](http://localhost:8090/superset/dashboard/respaldo-local-2025-10/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 304 números en este reporte, 304 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:20 UTC, corrida `20261124T021601Z-5b0c2e`).

- Tablero `respaldo-local-2025-10`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.690 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 304 de 304 se ven en los charts que cita su bloque.
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
| Resumen | 4.135.934 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +12,0 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.694.253 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 116,6 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +7,8 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.428.699 | EC.1 | `filas_archivo` · 2025-10 (y 1 más) |
| Calidad | 4.428.699 | EC.1 | `filas_archivo` · 2025-10 (y 1 más) |
| Calidad | 4.135.934 | EC.1 | `aceptadas` · 2025-10 |
| Calidad | 292.765 | EC.1 | `cuarentena` · 2025-10 |
| Calidad | 6,61 | EC.1 | `pct_cuarentena` · 2025-10 |
| Calidad | 900.005 | EC.1 | `con_advertencias` · 2025-10 |
| Calidad | 20,32 | EC.1 | `pct_advertencias` · 2025-10 |
| Calidad | 3.833.771 | EC.1 | `filas_archivo` · 2024-10 (y 1 más) |
| Calidad | 3.833.771 | EC.1 | `filas_archivo` · 2024-10 (y 1 más) |
| Calidad | 3.694.253 | EC.1 | `aceptadas` · 2024-10 |
| Calidad | 139.518 | EC.1 | `cuarentena` · 2024-10 |
| Calidad | 3,64 | EC.1 | `pct_cuarentena` · 2024-10 |
| Calidad | 395.875 | EC.1 | `con_advertencias` · 2024-10 |
| Calidad | 10,33 | EC.1 | `pct_advertencias` · 2024-10 |
| Calidad | 13 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 40 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 67.968 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,53 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.002 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +1,51 | EC.2 | `cambio_pp` · R02 |
| Calidad | 125.828 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,84 | EC.2 | `pct_mes` · R03 |
| Calidad | 81.768 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,13 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,71 | EC.2 | `cambio_pp` · R03 |
| Calidad | 108.735 | EC.2 | `filas_mes` · R04 |
| Calidad | 2,46 | EC.2 | `pct_mes` · R04 |
| Calidad | 61.426 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,60 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,85 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.013.197 | EC.2 | `filas_mes` · R05 |
| Calidad | 22,88 | EC.2 | `pct_mes` · R05 |
| Calidad | 429.665 | EC.2 | `filas_anterior` · R05 |
| Calidad | 11,21 | EC.2 | `pct_anterior` · R05 |
| Calidad | +11,67 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 2 | EC.2 | `pct_mes` · R02 (y 6 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 325.991 | EC.2 | `filas_mes` · R08 |
| Calidad | 7,36 | EC.2 | `pct_mes` · R08 |
| Calidad | 79.878 | EC.2 | `filas_anterior` · R08 |
| Calidad | 2,08 | EC.2 | `pct_anterior` · R08 |
| Calidad | +5,28 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.292 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.107 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 45.667 | EC.2 | `filas_mes` · R10 |
| Calidad | 1,03 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | +1,03 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 3,64 | EC.1 | `pct_cuarentena` · 2024-10 |
| Calidad | 6,61 | EC.1 | `pct_cuarentena` · 2025-10 |
| Calidad | 292.765 | EC.1 | `cuarentena` · 2025-10 |
| Calidad | 139.518 | EC.1 | `cuarentena` · 2024-10 |
| Calidad | 2,84 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,13 | EC.2 | `pct_anterior` · R03 |
| Calidad | 2,46 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,60 | EC.2 | `pct_anterior` · R04 |
| Calidad | +1,51 | EC.2 | `cambio_pp` · R02 |
| Calidad | 900.005 | EC.1 | `con_advertencias` · 2025-10 |
| Calidad | 20,3 | EC.1 | `pct_advertencias` · 2025-10 |
| Calidad | 22,9 | EC.2 | `pct_mes` · R05 |
| Calidad | 11,2 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 194.841 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 186.500 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 8.341 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 4,47 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 181.822 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 172.520 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 9.302 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 5,39 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 175.520 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 181.887 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -6.367 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -3,50 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 170.014 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 163.408 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 6.606 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 4,04 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 130.474 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 128.423 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 2.051 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 1,60 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 128.125 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 117.838 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 10.287 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 8,73 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 125.928 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 121.689 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 4.239 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 3,48 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 124.096 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 122.769 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 1.327 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 1,08 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 116.342 | E1.1 | `viajes_mes` · LaGuardia Airport Queens |
| Pregunta 1 | 115.354 | E1.1 | `viajes_anterior` · LaGuardia Airport Queens |
| Pregunta 1 | 988 | E1.1 | `variacion` · LaGuardia Airport Queens |
| Pregunta 1 | 0,86 | E1.1 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | 109.738 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 101.986 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | 7.752 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | 7,60 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | +0,9 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | +8,7 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan (y 1 más) |
| Pregunta 1 | −3,5 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 194.841 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +4,5 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | 3 | E1.1 | `puesto_anterior` · Midtown Center Manhattan (y 11 más) |
| Pregunta 1 | −3,5 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 9 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan (y 11 más) |
| Pregunta 1 | +0,9 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | 35,2 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 38,4 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 11.308 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 30.719 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +12,0 | E1.1 | `puesto_anterior` · Union Sq Manhattan (y 1 más) |
| Pregunta 2 | 16 | E2.1 | `puesto_anterior` · 0:00 (y 2 más) |
| Pregunta 2 | 235.339 | E2.1 | `viajes_mes` · 16:00 |
| Pregunta 2 | 32,29 | E2.1 | `ingreso_viaje_mes` · 16:00 |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 10 más) |
| Pregunta 2 | 24.200 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 37,10 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 16:00 | E2.1 | `puesto_anterior` · 0:00 (y 3 más) |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 12 más) |
| Pregunta 2 | 18:00 | E2.1 | `puesto_mes` · 0:00 (y 4 más) |
| Pregunta 2 | 32,29 | E2.1 | `ingreso_viaje_mes` · 16:00 (y 1 más) |
| Pregunta 2 | 37,10 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 235.339 | E2.1 | `viajes_mes` · 16:00 (y 1 más) |
| Pregunta 2 | 276.793 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 3 | 4.135.934 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 3.053.045 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 73,82 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 33.646 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 33.554 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,73 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 60.111 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 59.943 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,72 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 89.093 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 88.820 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,69 | E3.3 | `pct_con_peaje` · West Village Manhattan |
| Pregunta 3 | 109.198 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 108.795 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 99,63 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 59.424 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 59.177 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,58 | E3.3 | `pct_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 73,82 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.053.045 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 4.135.934 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 4 más) |
| Pregunta 3 | 45.667 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 682.354 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,77 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 2,11 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 2 más) |
| Pregunta 4 | 2.834.834 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 24,91 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 21,47 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 366.204 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 13.497 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge (y 4 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge (y 4 más) |
| Pregunta 4 | 4 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 45.833 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge (y 4 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge (y 4 más) |
| Pregunta 4 | 345.123 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 3,27 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 3,60 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 2 más) |
| Pregunta 4 | 2.828.683 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 24,73 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,97 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 452.812 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 5 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 14.609 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,03 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_media_pct_mes` · No charge (y 4 más) |
| Pregunta 4 | 4 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 39.375 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,03 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 24,91 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 24,73 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,5 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,0 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 92 | E4.1 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 9,7 | E4.1 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 21,2 | E4.1 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 345.123 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 682.354 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 3,27 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,77 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 11,2 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 22,9 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 76,6 | E4.1 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 68,5 | E4.1 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 358.652 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,04 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 205.167 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 156.460 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 373.321 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,15 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 217.015 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 159.549 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 3,9 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 373.321 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 358.652 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 12,0 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 10,1 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,7 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −5,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −1,9 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 57,15 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 57,04 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 59,00 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 57,60 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 4.135.934 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.694.253 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 441.681 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 11,96 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 19,17 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 20,29 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | -5,50 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 4.135.934 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.694.253 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +441.681 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +11,96 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 7,8 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 108,2 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 116,6 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 6 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 6 más) |
| Pregunta 6 | +11,5 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | +7 | E6.2 | `variacion_por_dia_pct` · martes |
| Pregunta 6 | +17 | E6.2 | `variacion_por_dia_pct` · viernes |
| Pregunta 6 | 5,50 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 20,29 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 19,17 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 14,20 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 13,98 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,56 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 10 | E6.5 | `valor_anterior` · Participación de Flex Fare (y 1 más) |
| Pregunta 6 | 21 | E6.5 | `valor_mes` · Participación de Flex Fare (y 2 más) |
| Pregunta 6 | 10,1 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,7 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,5 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 8,2 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 20,40 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 20,56 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 3,58 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,48 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 3,64 | EC.1 | `pct_cuarentena` · 2024-10 |
| Pregunta 6 | 6,61 | EC.1 | `pct_cuarentena` · 2025-10 |
| Pregunta 6 | 292.765 | EC.1 | `cuarentena` · 2025-10 |
| Pregunta 6 | 139.518 | EC.1 | `cuarentena` · 2024-10 |
| Pregunta 6 | 2,84 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,13 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 2,46 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,60 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +12,0 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +7,8 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +28,1 | C1.2 | `variacion_pct` · East Village Manhattan |
| Conclusiones | +21,5 | C1.2 | `variacion_pct` · West Chelsea/Hudson Yards Manhattan |
| Conclusiones | +33,7 | C1.2 | `variacion_pct` · Lower East Side Manhattan |
| Conclusiones | 73,8 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +9,3 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan |
| Conclusiones | +10,1 | C2.2 | `variacion_viajes_pct` · Greenwich Village South Manhattan |
| Conclusiones | +6,0 | C2.2 | `variacion_viajes_pct` · West Village Manhattan |
| Conclusiones | 3,58 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,48 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,20 | C3.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Conclusiones | 24,7 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 24,9 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 40 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 800,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 6,61 | C5.1 | `pct_cuarentena` · 2025-10 |
| Conclusiones | 3,64 | C5.1 | `pct_cuarentena` · 2024-10 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-10/#CHART-C5-2
