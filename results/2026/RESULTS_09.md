# Resultados: septiembre 2026 vs septiembre 2025

> En septiembre 2026 los taxis amarillos hicieron 3.667.332 viajes válidos, −8,2 % que en septiembre 2025 (3.996.265), con una recaudación de US$ 118,0 M (+2,4 %).

| | |
|---|---|
| Comando | `make all MES=2026-09 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-09.parquet` y `yellow_tripdata_2025-09.parquet` |
| Corrida | `20261118T045143Z-2dc8eb`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=09/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09 | `yellow_tripdata_2026-09.parquet` | 3.876.044 | 3.876.044 | 3.667.332 | 208.712 | 5,38 % | 1.093.003 (28,20 %) | sí |
| 2025-09 | `yellow_tripdata_2025-09.parquet` | 4.251.015 | 4.251.015 | 3.996.265 | 254.750 | 5,99 % | 1.010.489 (23,77 %) | sí |

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

- La cuarentena baja del 5,99 % al 5,38 % de las filas leídas (208.712 filas en septiembre 2026 y 254.750 en septiembre 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,80 % contra 2,93 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,24 % contra 1,35 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,47 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 1.093.003 filas aceptadas de septiembre 2026 (28,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 31,0 %, contra 25,6 % en septiembre 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de septiembre 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de septiembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve caen (entre −3,7 % en East Village y −13,8 % en JFK Airport) y una se mantiene. Upper East Side South lidera con 165.197 viajes (−7,5 %). Respecto de septiembre 2025 entran al top 10 Lincoln Square East y East Village y salen Union Sq y Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −13,8 % y LaGuardia (fuera del top) cae −7,2 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−8,2 %). La concentración casi no cambia: el top 10 reúne el 33,4 % de los pickups (33,7 % en 2025). Fuera de Manhattan, el Bronx cae −36,6 % en sus pickups (29.050 → 18.428), aunque sobre una base chica, contra −8,2 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 5:00 en 2026 (US$ 37,70) y las 16:00 en 2025 (US$ 33,99). Es una hora de poco volumen (35.231 viajes, contra 233.026 a las 20:00, la hora pico de demanda). Gana porque a esa hora pesan los viajes largos: el 19,3 % de sus viajes toca JFK o LaGuardia (contra 8,3 % en todo el mes) y la distancia media es de 6,02 millas (contra 3,67).

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

**Interpretación:** El 75,83 % de los viajes de septiembre 2026 pagó cbd_congestion_fee (2.780.820 de 3.667.332, siempre US$ 0,75). Las cinco zonas con mayor proporción (West Village, Greenwich Village South, East Village, SoHo y Lower East Side, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En septiembre 2025 lo pagaba el 74,01 % de los viajes: la proporción sube +1,8 pp. La regla R10 marcó 9.618 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina baja: 24,79 % de la tarifa en 2026 frente a 25,82 % en 2025 (22,1 % y 21,4 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 24,7 % al 29,4 % de los viajes (827.190 → 1.078.694 con tarifa > 0) y cuya propina se mantiene en torno al 1,3 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 25,6 % al 31,0 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 65,2 % al 61,8 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 9,4 % (336.219 → 304.762) mientras el total de la ciudad baja un 8,2 %, así que su peso cae del 8,4 % al 8,3 % de los viajes. Por aeropuerto, JFK cae −12,5 % y LaGuardia cae −5,1 %. La tarifa promedio baja de US$ 58,25 a US$ 56,49 (−3,0 %), pero esa baja está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 323.800,27 (de JFK Airport a Midtown South, 11,8 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 57,26 a US$ 56,46 (−1,4 %), y la mediana baja de US$ 58,30 a US$ 56,20. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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

**Interpretación:**

- Septiembre 2026 tuvo 3.667.332 viajes válidos contra 3.996.265 en septiembre 2025: −328.933 viajes (−8,23 %). La recaudación total (total_amount) crece un 2,4 %, de US$ 115,2 M a US$ 118,0 M.
- El calendario favorece a septiembre 2026: septiembre 2026 tuvo 5 miércoles, y septiembre 2025, 5 lunes (días flojos). Con el calendario de 2025 la variación sería −8,7 %. Todos los días de la semana caen (por día), entre −7 % y −12 %, así que la baja es general.
- La tarifa promedio sube un 15,08 % (de US$ 19,99 a US$ 23,00); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 323.800) la suba es del 15,6 % (de US$ 19,90 a US$ 23,00). La mediana pasa de US$ 14,90 a US$ 17,20 (+15,4 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de septiembre 2026 hay más viajes Flex Fare, que son más caros (US$ 29,42 contra US$ 20,32 del resto) y pasan del 25 % al 29 % de los viajes y menos viajes de más de 10 millas (del 8,3 % al 8,0 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 1,6 % (de US$ 20,65 a US$ 20,32).
- Calidad: la cuarentena baja del 5,99 % al 5,38 % de las filas leídas (208.712 filas en septiembre 2026 y 254.750 en septiembre 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,80 % contra 2,93 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,24 % contra 1,35 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en septiembre 2026 (−8,2 % de viajes, +2,4 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,8 %), Midtown Center (−13,0 %) y Midtown East (−13,1 %).
- El peaje de congestión (CBD) alcanza al 75,8 % de los viajes de septiembre 2026, contra 74,0 % en septiembre 2025.
- El viaje promedio es más largo (3,67 contra 3,63 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,90 → US$ 17,20). La propina con tarjeta baja (25,8 % → 24,8 %).
- Los promedios son frágiles: 58 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 323.800,27, en 2025) alcanzan para mover la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (septiembre 2026: columna nueva ignorada: request_source). La cuarentena es del 5,38 % y del 5,99 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-09 INGEST_MODE=direct WAREHOUSE=duckdb`.
