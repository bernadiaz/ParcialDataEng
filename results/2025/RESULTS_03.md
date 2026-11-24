# Resultados: marzo 2025 vs marzo 2024

> En marzo 2025 los taxis amarillos hicieron 3.955.206 viajes válidos, +14,5 % que en marzo 2024 (3.453.501), con una recaudación de US$ 107,4 M (+12,1 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-03 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-03.parquet` y `yellow_tripdata_2024-03.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-03`](http://localhost:8090/superset/dashboard/respaldo-local-2025-03/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T015201Z-299545`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=03/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-03 | `yellow_tripdata_2025-03.parquet` | 4.145.257 | 4.145.257 | 3.955.206 | 190.051 | 4,58 % | 879.350 (21,21 %) | sí |
| 2024-03 | `yellow_tripdata_2024-03.parquet` | 3.582.628 | 3.582.628 | 3.453.501 | 129.127 | 3,60 % | 421.321 (11,76 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-03 | 2024-03 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 33 (0,00 %) | 23 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 22.280 (0,54 %) | 1.128 (0,03 %) | +0,51 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 103.936 (2,51 %) | 87.290 (2,44 %) | +0,07 pp |
| R04 | reject | Total cobrado faltante o negativo. | 68.686 (1,66 %) | 44.311 (1,24 %) | +0,42 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 939.378 (22,66 %) | 466.562 (13,02 %) | +9,64 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 213.335 (5,15 %) | 62.863 (1,75 %) | +3,39 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.050 (0,03 %) | 1.241 (0,03 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 47.166 (1,14 %) | 0 (0,00 %) | +1,14 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 3,60 % al 4,58 % de las filas leídas (190.051 filas en marzo 2025 y 129.127 en marzo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,51 % contra 2,44 %) y R04 (total cobrado faltante o negativo: 1,66 % contra 1,24 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +0,51 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 879.350 filas aceptadas de marzo 2025 (21,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 22,7 %, contra 13,0 % en marzo 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de marzo 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de marzo 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Midtown Center | 175.034 | 158.985 | 16.049 | 10,09 |
| Manhattan | Upper East Side South | 165.092 | 152.243 | 12.849 | 8,44 |
| Queens | JFK Airport | 148.219 | 149.422 | -1.203 | -0,81 |
| Manhattan | Upper East Side North | 147.810 | 142.714 | 5.096 | 3,57 |
| Manhattan | Times Sq/Theatre District | 130.690 | 118.562 | 12.128 | 10,23 |
| Manhattan | Penn Station/Madison Sq West | 127.849 | 111.779 | 16.070 | 14,38 |
| Manhattan | Midtown East | 123.951 | 120.656 | 3.295 | 2,73 |
| Manhattan | Lincoln Square East | 113.249 | 111.844 | 1.405 | 1,26 |
| Manhattan | Union Sq | 110.035 | 94.609 | 15.426 | 16,31 |
| Manhattan | East Village | 106.630 | 89.493 | 17.137 | 19,15 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +1,3 % en Lincoln Square East y +19,1 % en East Village) y una cae (JFK Airport −0,8 %). Midtown Center lidera con 175.034 viajes (+10,1 %). Respecto de marzo 2024 entran al top 10 Union Sq y East Village y salen LaGuardia Airport y Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −0,8 % y LaGuardia (fuera del top) cae −1,2 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 34,1 % de los pickups, frente al 36,8 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (9.568 → 32.333), aunque sobre una base chica, contra +14,5 % del total.

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
| 2025 | 3 | 5 | 31.994 | 33,56 |
| 2024 | 3 | 5 | 21.430 | 35,57 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,56 en 2025 y US$ 35,57 en 2024. Es una hora de poco volumen (31.994 viajes, contra 272.709 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,2 % de sus viajes toca JFK o LaGuardia (contra 8,0 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,33). En 2025 los viajes de aeropuerto son menos (del 21,9 % al 18,2 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 5,7 %.

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
| ALL ZONES |  | 3.955.206 | 2.936.806 | 74,25 |
| SoHo | Manhattan | 34.502 | 34.444 | 99,83 |
| Greenwich Village North | Manhattan | 58.176 | 58.035 | 99,76 |
| West Village | Manhattan | 96.000 | 95.764 | 99,75 |
| Little Italy/NoLiTa | Manhattan | 45.862 | 45.748 | 99,75 |
| Greenwich Village South | Manhattan | 64.056 | 63.895 | 99,75 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 74,25 % de los viajes de marzo 2025 pagó cbd_congestion_fee (2.936.806 de 3.955.206, un cobro medio de US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village North, West Village, Little Italy/NoLiTa y Greenwich Village South, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En marzo 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 47.166 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 3 | 0 | Flex Fare | 725.934 | 1,97 | 2,03 |
| 2025 | 3 | 1 | Credit card | 2.663.715 | 26,10 | 22,65 |
| 2025 | 3 | 2 | Cash | 377.599 | 0,00 | 0,00 |
| 2025 | 3 | 3 | No charge | 14.177 | 0,01 | 0,01 |
| 2025 | 3 | 4 | Dispute | 44.704 | 0,05 | 0,05 |
| 2024 | 3 | 0 | Flex Fare | 364.912 | 3,40 | 3,67 |
| 2024 | 3 | 1 | Credit card | 2.575.194 | 25,18 | 22,39 |
| 2024 | 3 | 2 | Cash | 457.534 | 0,00 | 0,00 |
| 2024 | 3 | 3 | No charge | 12.570 | 0,01 | 0,01 |
| 2024 | 3 | 4 | Dispute | 28.433 | 0,19 | 0,11 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina sube: 26,10 % de la tarifa en 2025 frente a 25,18 % en 2024 (22,6 % y 22,4 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,0 % al 21,6 % de los viajes (364.912 → 725.934 con tarifa > 0) y cuya propina cae del 3,40 % al 1,97 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 13,0 % al 22,7 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,6 % al 67,3 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 3 | 318.287 | 55,29 | 177.567 | 143.511 |
| 2024 | 3 | 320.254 | 55,70 | 179.245 | 144.271 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 0,6 % (320.254 → 318.287) mientras el total de la ciudad sube un 14,5 %, así que su peso cae del 9,3 % al 8,0 % de los viajes. Por aeropuerto, JFK cae −0,9 % y LaGuardia cae −0,5 %. La tarifa promedio baja de US$ 55,70 a US$ 55,29 (−0,7 %), y la mediana baja de US$ 54,80 a US$ 54,10. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.955.206 | 3.453.501 | 501.705 | 14,53 | 18,40 | 19,06 | -3,47 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Marzo 2025 tuvo 3.955.206 viajes válidos contra 3.453.501 en marzo 2024: +501.705 viajes (+14,53 %). La recaudación total (total_amount) crece un 12,1 %, de US$ 95,8 M a US$ 107,4 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario juega en contra de marzo 2025: marzo 2025 tuvo 5 lunes (días flojos), y marzo 2024, 5 viernes (días fuertes). Con el calendario de 2024 la variación sería +15,3 %. Todos los días de la semana crecen (por día), entre +9 % y +24 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 3,47 % (de US$ 19,06 a US$ 18,40). La mediana no cambia (US$ 13,50): no bajaron las tarifas, cambió la mezcla de viajes.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de marzo 2025 hay más viajes Flex Fare, que son más baratos (US$ 17,19 contra US$ 18,73 del resto) y pasan del 11 % al 22 % de los viajes, menos viajes a aeropuertos (del 9,3 % al 8,0 %) y menos viajes de más de 10 millas (del 7,7 % al 7,1 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,0 % (de US$ 19,11 a US$ 18,73).
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 3,60 % al 4,58 % de las filas leídas (190.051 filas en marzo 2025 y 129.127 en marzo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,51 % contra 2,44 %) y R04 (total cobrado faltante o negativo: 1,66 % contra 1,24 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en marzo 2025 (+14,5 % de viajes, +12,1 % de recaudación). Las zonas que más suman viajes son East Village (+19,1 %), Penn Station/Madison Sq West (+14,4 %) y Midtown Center (+10,1 %), mientras los aeropuertos se quedan atrás.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 74,3 % de los viajes de marzo 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +25,6 %, Greenwich Village North +11,8 % y West Village +12,4 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es igual de largo (3,33 contra 3,36 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 13,50, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta sube (25,2 % → 26,1 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 29 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 999,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (marzo 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,58 % y del 3,60 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-03 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-03`](http://localhost:8090/superset/dashboard/respaldo-local-2025-03/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 309 números en este reporte, 309 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:17 UTC, corrida `20261124T021601Z-5b0c2e`).

- Tablero `respaldo-local-2025-03`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.674 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 309 de 309 se ven en los charts que cita su bloque.
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
| Resumen | 3.955.206 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +14,5 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.453.501 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 107,4 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +12,1 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.145.257 | EC.1 | `filas_archivo` · 2025-03 (y 1 más) |
| Calidad | 4.145.257 | EC.1 | `filas_archivo` · 2025-03 (y 1 más) |
| Calidad | 3.955.206 | EC.1 | `aceptadas` · 2025-03 |
| Calidad | 190.051 | EC.1 | `cuarentena` · 2025-03 |
| Calidad | 4,58 | EC.1 | `pct_cuarentena` · 2025-03 |
| Calidad | 879.350 | EC.1 | `con_advertencias` · 2025-03 |
| Calidad | 21,21 | EC.1 | `pct_advertencias` · 2025-03 |
| Calidad | 3.582.628 | EC.1 | `filas_archivo` · 2024-03 (y 1 más) |
| Calidad | 3.582.628 | EC.1 | `filas_archivo` · 2024-03 (y 1 más) |
| Calidad | 3.453.501 | EC.1 | `aceptadas` · 2024-03 |
| Calidad | 129.127 | EC.1 | `cuarentena` · 2024-03 |
| Calidad | 3,60 | EC.1 | `pct_cuarentena` · 2024-03 |
| Calidad | 421.321 | EC.1 | `con_advertencias` · 2024-03 |
| Calidad | 11,76 | EC.1 | `pct_advertencias` · 2024-03 |
| Calidad | 33 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 23 | EC.2 | `filas_anterior` · R01 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 22.280 | EC.2 | `filas_mes` · R02 |
| Calidad | 0,54 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.128 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | +0,51 | EC.2 | `cambio_pp` · R02 |
| Calidad | 103.936 | EC.2 | `filas_mes` · R03 |
| Calidad | 2,51 | EC.2 | `pct_mes` · R03 |
| Calidad | 87.290 | EC.2 | `filas_anterior` · R03 |
| Calidad | 2,44 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,07 | EC.2 | `cambio_pp` · R03 |
| Calidad | 68.686 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,66 | EC.2 | `pct_mes` · R04 |
| Calidad | 44.311 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,24 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,42 | EC.2 | `cambio_pp` · R04 |
| Calidad | 939.378 | EC.2 | `filas_mes` · R05 |
| Calidad | 22,66 | EC.2 | `pct_mes` · R05 |
| Calidad | 466.562 | EC.2 | `filas_anterior` · R05 |
| Calidad | 13,02 | EC.2 | `pct_anterior` · R05 |
| Calidad | +9,64 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | 213.335 | EC.2 | `filas_mes` · R08 |
| Calidad | 5,15 | EC.2 | `pct_mes` · R08 |
| Calidad | 62.863 | EC.2 | `filas_anterior` · R08 |
| Calidad | 1,75 | EC.2 | `pct_anterior` · R08 |
| Calidad | +3,39 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.050 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | 1.241 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 2 más) |
| Calidad | −0,01 | EC.2 | `cambio_pp` · R09 |
| Calidad | 47.166 | EC.2 | `filas_mes` · R10 |
| Calidad | 1,14 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 14 más) |
| Calidad | +1,14 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 3,60 | EC.1 | `pct_cuarentena` · 2024-03 |
| Calidad | 4,58 | EC.1 | `pct_cuarentena` · 2025-03 |
| Calidad | 190.051 | EC.1 | `cuarentena` · 2025-03 |
| Calidad | 129.127 | EC.1 | `cuarentena` · 2024-03 |
| Calidad | 2,51 | EC.2 | `pct_mes` · R03 |
| Calidad | 2,44 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,66 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,24 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,51 | EC.2 | `cambio_pp` · R02 |
| Calidad | 879.350 | EC.1 | `con_advertencias` · 2025-03 |
| Calidad | 21,2 | EC.1 | `pct_advertencias` · 2025-03 |
| Calidad | 22,7 | EC.2 | `pct_mes` · R05 |
| Calidad | 13,0 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 175.034 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 158.985 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 16.049 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 10,09 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 165.092 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 152.243 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 12.849 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 8,44 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 148.219 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 149.422 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -1.203 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -0,81 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 147.810 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 142.714 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 5.096 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 3,57 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 130.690 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 118.562 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 12.128 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 10,23 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 127.849 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 111.779 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 16.070 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 14,38 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 123.951 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 120.656 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 3.295 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 2,73 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 113.249 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 111.844 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 1.405 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 1,26 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 110.035 | E1.1 | `viajes_mes` · Union Sq Manhattan |
| Pregunta 1 | 94.609 | E1.1 | `viajes_anterior` · Union Sq Manhattan |
| Pregunta 1 | 15.426 | E1.1 | `variacion` · Union Sq Manhattan |
| Pregunta 1 | 16,31 | E1.1 | `variacion_pct` · Union Sq Manhattan |
| Pregunta 1 | 106.630 | E1.1 | `viajes_mes` · East Village Manhattan |
| Pregunta 1 | 89.493 | E1.1 | `viajes_anterior` · East Village Manhattan |
| Pregunta 1 | 17.137 | E1.1 | `variacion` · East Village Manhattan |
| Pregunta 1 | 19,15 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | +1,3 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan (y 1 más) |
| Pregunta 1 | +19,1 | E1.1 | `variacion_pct` · East Village Manhattan |
| Pregunta 1 | −0,8 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 175.034 | E1.1 | `viajes_mes` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | +10,1 | E1.1 | `variacion_pct` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | 3 | E1.1 | `puesto_mes` · JFK Airport Queens (y 11 más) |
| Pregunta 1 | −0,8 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −1,2 | E1.3 | `variacion_pct` · LaGuardia Airport Queens (y 1 más) |
| Pregunta 1 | 34,1 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 36,8 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 9.568 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 32.333 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +14,5 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 9 más) |
| Pregunta 2 | 31.994 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 33,56 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 5 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 9 más) |
| Pregunta 2 | 21.430 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 35,57 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 5:00 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 11 más) |
| Pregunta 2 | 18:00 | E2.1 | `pct_aeropuerto_mes` · 5:00 (y 6 más) |
| Pregunta 2 | 5:00 | E2.1 | `pct_aeropuerto_mes` · 1:00 (y 11 más) |
| Pregunta 2 | 33,56 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 2 más) |
| Pregunta 2 | 35,57 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 2 más) |
| Pregunta 2 | 31.994 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 272.709 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 18,2 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,0 | E2.1 | `hora` · 8:00 (y 3 más) |
| Pregunta 2 | 5,71 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,33 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 21,9 | E2.1 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 18,2 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 5,7 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 2 más) |
| Pregunta 3 | 3.955.206 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.936.806 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 74,25 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 34.502 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 34.444 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,83 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 58.176 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 58.035 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,76 | E3.3 | `pct_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 96.000 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 95.764 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,75 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 2 más) |
| Pregunta 3 | 45.862 | E3.3 | `viajes` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 45.748 | E3.3 | `viajes_con_peaje` · Little Italy/NoLiTa Manhattan |
| Pregunta 3 | 99,75 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 2 más) |
| Pregunta 3 | 64.056 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 63.895 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,75 | E3.3 | `pct_con_peaje` · West Village Manhattan (y 2 más) |
| Pregunta 3 | 74,25 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.936.806 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.955.206 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 4 más) |
| Pregunta 3 | 47.166 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 725.934 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,97 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 2,03 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 2 más) |
| Pregunta 4 | 2.663.715 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 26,10 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,65 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 377.599 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 14.177 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 4 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 44.704 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_mes` · Dispute (y 1 más) |
| Pregunta 4 | 0,05 | E4.1 | `propina_media_pct_mes` · Dispute (y 1 más) |
| Pregunta 4 | 364.912 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 3,40 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 3,67 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `payment_type` · Credit card (y 2 más) |
| Pregunta 4 | 2.575.194 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,18 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,39 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 457.534 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 12.570 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 4 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 28.433 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,19 | E4.1 | `propina_media_pct_anterior` · Dispute |
| Pregunta 4 | 0,11 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 26,10 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,18 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,6 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,4 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 94 | E4.1 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 11,0 | E4.1 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 21,6 | E4.1 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 364.912 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 725.934 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 3,40 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,97 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 13,0 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 22,7 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 74,6 | E4.1 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 67,3 | E4.1 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 318.287 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,29 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 177.567 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 143.511 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 320.254 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,70 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 179.245 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 144.271 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 0,6 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia (y 1 más) |
| Pregunta 5 | 320.254 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 318.287 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 14,5 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,3 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,0 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | −0,9 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −0,5 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 55,70 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,29 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −0,7 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto (y 2 más) |
| Pregunta 5 | 54,80 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 54,10 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.955.206 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.453.501 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 501.705 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 14,53 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 18,40 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,06 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | -3,47 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 3.955.206 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.453.501 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +501.705 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +14,53 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 12,1 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 95,8 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 107,4 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 5 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 5 más) |
| Pregunta 6 | +15,3 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | +9 | E6.2 | `variacion_por_dia_pct` · martes (y 1 más) |
| Pregunta 6 | +24 | E6.2 | `variacion_por_dia_pct` · sábado (y 1 más) |
| Pregunta 6 | 3,47 | E6.1 | `variacion_pct` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,06 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 18,40 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 13,50 | E6.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Pregunta 6 | 17,19 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 18,73 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 11 | E6.5 | `valor_anterior` · Participación de Flex Fare (y 1 más) |
| Pregunta 6 | 22 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 9,3 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,0 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 7,7 | E6.5 | `valor_anterior` · Viajes de más de 10 millas (y 3 más) |
| Pregunta 6 | 7,1 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 2,0 | E6.5 | `variacion_pct` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 19,11 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 18,73 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare (y 1 más) |
| Pregunta 6 | 3,60 | EC.1 | `pct_cuarentena` · 2024-03 |
| Pregunta 6 | 4,58 | EC.1 | `pct_cuarentena` · 2025-03 |
| Pregunta 6 | 190.051 | EC.1 | `cuarentena` · 2025-03 |
| Pregunta 6 | 129.127 | EC.1 | `cuarentena` · 2024-03 |
| Pregunta 6 | 2,51 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 2,44 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,66 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,24 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +14,5 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +12,1 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +19,1 | C1.2 | `variacion_pct` · East Village Manhattan |
| Conclusiones | +14,4 | C1.2 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Conclusiones | +10,1 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | 74,3 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +25,6 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan |
| Conclusiones | +11,8 | C2.2 | `variacion_viajes_pct` · Greenwich Village North Manhattan |
| Conclusiones | +12,4 | C2.2 | `variacion_viajes_pct` · West Village Manhattan |
| Conclusiones | 3,33 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,36 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 13,50 | C3.1 | `valor_mes` · Tarifa mediana (y 1 más) |
| Conclusiones | 25,2 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 26,1 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 29 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses (y 17 más) |
| Conclusiones | 999,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,58 | C5.1 | `pct_cuarentena` · 2025-03 |
| Conclusiones | 3,60 | C5.1 | `pct_cuarentena` · 2024-03 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-03/#CHART-C5-2
