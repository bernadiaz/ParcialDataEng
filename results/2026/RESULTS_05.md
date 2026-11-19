# Resultados: mayo 2026 vs mayo 2025

> En mayo 2026 los taxis amarillos hicieron 3.912.688 viajes válidos, −8,7 % que en mayo 2025 (4.284.351), con una recaudación de US$ 119,5 M (−1,0 %).

| | |
|---|---|
| Comando | `make all MES=2026-05 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-05.parquet` y `yellow_tripdata_2025-05.parquet` |
| Corrida | `20261118T045135Z-162a6f`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=05/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-05 | `yellow_tripdata_2026-05.parquet` | 4.090.836 | 4.090.836 | 3.912.688 | 178.148 | 4,35 % | 894.718 (21,87 %) | sí |
| 2025-05 | `yellow_tripdata_2025-05.parquet` | 4.591.845 | 4.591.845 | 4.284.351 | 307.494 | 6,70 % | 1.095.990 (23,87 %) | sí |

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

- La cuarentena baja del 6,70 % al 4,35 % de las filas leídas (178.148 filas en mayo 2026 y 307.494 en mayo 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,77 % contra 3,08 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,27 % contra 1,40 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −2,09 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 894.718 filas aceptadas de mayo 2026 (21,9 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 23,7 %, contra 26,6 % en mayo 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de mayo 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de mayo 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan y las diez caen, entre −2,1 % (Upper East Side North) y −19,2 % (JFK Airport). Upper East Side South lidera con 190.900 viajes (−2,7 %). Respecto de mayo 2025 entran al top 10 Upper West Side South y East Village y salen LaGuardia Airport y Union Sq. En los aeropuertos, JFK (puesto 4 del top) cae −19,2 % y LaGuardia (fuera del top) cae −14,0 %: los aeropuertos van peor que el total de la ciudad (−8,7 %). La concentración casi no cambia: el top 10 reúne el 33,7 % de los pickups (34,1 % en 2025). Fuera de Manhattan, Queens cae −19,2 % en sus pickups (413.861 → 334.597), contra −8,7 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,74 en 2026 y US$ 33,20 en 2025. Es una hora de poco volumen (35.166 viajes, contra 254.138 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 16,7 % de sus viajes toca JFK o LaGuardia (contra 7,9 % en todo el mes) y la distancia media es de 6,13 millas (contra 3,52). El ingreso por viaje de esa hora sube un 10,7 % aunque los viajes de aeropuerto son menos (del 18,3 % al 16,7 % de los viajes de las 5:00): lo explican las tarifas y recargos de 2026.

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

**Interpretación:** El 66,74 % de los viajes de mayo 2026 pagó cbd_congestion_fee (2.611.323 de 3.912.688, siempre US$ 0,75). Las cinco zonas con mayor proporción (Penn Station/Madison Sq West, Midtown East, Sutton Place/Turtle Bay North, Midtown North y Midtown Center, entre 94,7 % y 96,8 %) están todas en Manhattan, dentro de la zona de peaje. En mayo 2025 lo pagaba el 73,22 % de los viajes: la proporción baja −6,5 pp. La regla R10 marcó 9.689 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina baja: 24,54 % de la tarifa en 2026 frente a 25,36 % en 2025 (21,1 % y 22,2 % ponderada), y deja propina el 90 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 25,0 % al 22,5 % de los viajes (877.068 → 877.870 con tarifa > 0) y cuya propina sube del 1,70 % al 2,07 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 bajan del 26,6 % al 23,7 % de las filas leídas. La tarjeta gana peso entre las formas de pago: del 64,5 % al 68,0 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 17,3 % (372.036 → 307.572) mientras el total de la ciudad baja un 8,7 %, así que su peso cae del 8,7 % al 7,9 % de los viajes. Por aeropuerto, JFK cae −19,7 % y LaGuardia cae −14,4 %. La tarifa promedio baja de US$ 57,27 a US$ 56,13 (−2,0 %), y la mediana baja de US$ 58,00 a US$ 55,50. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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

**Interpretación:**

- Mayo 2026 tuvo 3.912.688 viajes válidos contra 4.284.351 en mayo 2025: −371.663 viajes (−8,67 %). La recaudación total (total_amount) cae un 1,0 %, de US$ 120,7 M a US$ 119,5 M.
- Parte de la caída es de calendario: mayo 2026 tuvo 5 domingos (días flojos), y mayo 2025, 5 jueves (días fuertes). Con el calendario de 2025 la variación sería −8,1 %. Todos los días de la semana caen (por día), entre −5 % y −12 %, así que la baja es general.
- La tarifa promedio sube un 11,26 % (de US$ 19,29 a US$ 21,46). La mediana pasa de US$ 14,20 a US$ 16,30 (+14,8 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de mayo 2026 hay menos viajes Flex Fare, que son más caros (US$ 25,56 contra US$ 20,27 del resto) y pasan del 25 % al 22 % de los viajes, menos viajes a aeropuertos (del 8,7 % al 7,9 %) y menos viajes de más de 10 millas (del 7,9 % al 7,7 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,17 a US$ 20,27).
- Calidad: la cuarentena baja del 6,70 % al 4,35 % de las filas leídas (178.148 filas en mayo 2026 y 307.494 en mayo 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,77 % contra 3,08 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,27 % contra 1,40 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en mayo 2026 (−8,7 % de viajes, −1,0 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−19,2 %), Times Sq/Theatre District (−16,6 %) y Midtown Center (−11,2 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 66,7 % de los viajes de mayo 2026, contra 73,2 % en mayo 2025.
- El viaje promedio es igual de largo (3,52 contra 3,55 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 16,30). La propina con tarjeta baja (25,4 % → 24,5 %).
- Hay 52 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 1.755,80, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 4,35 % y del 6,70 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-05 INGEST_MODE=direct WAREHOUSE=duckdb`.
