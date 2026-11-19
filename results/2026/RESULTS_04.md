# Resultados: abril 2026 vs abril 2025

> En abril 2026 los taxis amarillos hicieron 3.674.624 viajes válidos, −2,7 % que en abril 2025 (3.776.409), con una recaudación de US$ 110,6 M (+6,1 %).

| | |
|---|---|
| Comando | `make all MES=2026-04 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-04.parquet` y `yellow_tripdata_2025-04.parquet` |
| Corrida | `20261118T045132Z-efe355`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=04/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-04 | `yellow_tripdata_2026-04.parquet` | 3.831.240 | 3.831.240 | 3.674.624 | 156.616 | 4,09 % | 755.063 (19,71 %) | sí |
| 2025-04 | `yellow_tripdata_2025-04.parquet` | 3.970.553 | 3.970.553 | 3.776.409 | 194.144 | 4,89 % | 721.657 (18,18 %) | sí |

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

- La cuarentena baja del 4,89 % al 4,09 % de las filas leídas (156.616 filas en abril 2026 y 194.144 en abril 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,44 % contra 2,31 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 0,88 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,44 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 755.063 filas aceptadas de abril 2026 (19,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 21,2 %, contra 19,4 % en abril 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de abril 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de abril 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan y las diez caen, entre −0,6 % (Upper East Side North) y −14,1 % (Times Sq/Theatre District). Upper East Side South lidera con 176.545 viajes (−1,2 %). Respecto de abril 2025 entra al top 10 Upper West Side South y sale Union Sq. En los aeropuertos, JFK (puesto 4 del top) cae −2,0 % y LaGuardia (puesto 9 del top) cae −7,6 %: LaGuardia va peor que el total de la ciudad y JFK queda en línea con él (−2,7 %). La demanda además se reparte más: el top 10 concentra el 34,6 % de los pickups, frente al 35,6 % de 2025. Fuera de Manhattan, el Bronx crece +23,6 % en sus pickups (28.212 → 34.866), aunque sobre una base chica, contra −2,7 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,04 en 2026 y US$ 32,73 en 2025. Es una hora de poco volumen (31.310 viajes, contra 237.020 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 14,6 % de sus viajes toca JFK o LaGuardia (contra 8,0 % en todo el mes) y la distancia media es de 6,09 millas (contra 3,52). En 2026 la distancia media sube (de 5,75 a 6,09 millas), por eso el ingreso por viaje sube un 10,1 %, aunque los viajes de aeropuerto son menos (del 18,0 % al 14,6 % de los viajes de las 5:00).

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

**Interpretación:** El 71,74 % de los viajes de abril 2026 pagó cbd_congestion_fee (2.636.125 de 3.674.624, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Midtown North, alrededor del 99 %) están todas en Manhattan, dentro de la zona de peaje. En abril 2025 lo pagaba el 73,95 % de los viajes: la proporción baja −2,2 pp. La regla R10 marcó 9.706 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina baja: 24,99 % de la tarifa en 2026 frente a 25,94 % en 2025 (21,1 % y 22,6 % ponderada), y deja propina el 90 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. También pesa Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 18,4 % al 20,1 % de los viajes (591.396 → 738.979 con tarifa > 0) y cuya propina se mantiene en torno al 2,0 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 19,4 % al 21,2 % de las filas leídas. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 6,9 % (314.242 → 292.622) mientras el total de la ciudad baja un 2,7 %, así que su peso cae del 8,3 % al 8,0 % de los viajes. Por aeropuerto, JFK cae −5,2 % y LaGuardia cae −9,1 %. La tarifa promedio baja de US$ 55,78 a US$ 55,29 (−0,9 %), y la mediana baja de US$ 54,80 a US$ 53,40. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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

**Interpretación:**

- Abril 2026 tuvo 3.674.624 viajes válidos contra 3.776.409 en abril 2025: −101.785 viajes (−2,70 %). La recaudación total (total_amount) crece un 6,1 %, de US$ 104,2 M a US$ 110,6 M.
- El calendario casi no influye: abril 2026 tuvo 5 jueves (días fuertes), y abril 2025, 5 martes (días flojos). Por día de la semana la variación va de −7 % a +2 %: el cambio no es parejo.
- La tarifa promedio sube un 13,01 % (de US$ 18,65 a US$ 21,08). La mediana pasa de US$ 13,50 a US$ 15,60 (+15,6 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de abril 2026 hay más viajes Flex Fare, que son más caros (US$ 25,75 contra US$ 19,90 del resto) y pasan del 18 % al 20 % de los viajes, menos viajes a aeropuertos (del 8,3 % al 8,0 %) y más viajes de más de 10 millas (del 7,3 % al 7,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 4,6 % (de US$ 19,03 a US$ 19,90). El viaje promedio es más largo: 3,52 contra 3,37 millas.
- Calidad: la cuarentena baja del 4,89 % al 4,09 % de las filas leídas (156.616 filas en abril 2026 y 194.144 en abril 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,44 % contra 2,31 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 0,88 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae levemente en abril 2026 (−2,7 % de viajes, +6,1 % de recaudación). Las zonas que más pierden viajes son Times Sq/Theatre District (−14,1 %), Midtown Center (−10,2 %) y Midtown South (−12,1 %).
- El peaje de congestión (CBD) alcanza al 71,7 % de los viajes de abril 2026, contra 73,9 % en abril 2025.
- El viaje promedio es más largo (3,52 contra 3,37 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 13,50 → US$ 15,60). La propina con tarjeta baja (25,9 % → 25,0 %).
- Hay 33 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 980,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 4,09 % y del 4,89 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-04 INGEST_MODE=direct WAREHOUSE=duckdb`.
