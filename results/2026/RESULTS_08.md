# Resultados: agosto 2026 vs agosto 2025

> En agosto 2026 los taxis amarillos hicieron 3.163.698 viajes válidos, −5,3 % que en agosto 2025 (3.339.362), con una recaudación de US$ 95,4 M (+2,9 %).

| | |
|---|---|
| Comando | `make all MES=2026-08 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-08.parquet` y `yellow_tripdata_2025-08.parquet` |
| Corrida | `20261118T045141Z-c13895`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=08/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-08 | `yellow_tripdata_2026-08.parquet` | 3.336.716 | 3.336.716 | 3.163.698 | 173.018 | 5,19 % | 849.450 (25,46 %) | sí |
| 2025-08 | `yellow_tripdata_2025-08.parquet` | 3.574.091 | 3.574.091 | 3.339.362 | 234.729 | 6,57 % | 831.289 (23,26 %) | sí |

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

- La cuarentena baja del 6,57 % al 5,19 % de las filas leídas (173.018 filas en agosto 2026 y 234.729 en agosto 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,57 % contra 2,95 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 1,34 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −2,03 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 849.450 filas aceptadas de agosto 2026 (25,5 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 27,8 %, contra 25,3 % en agosto 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de agosto 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de agosto 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, cuatro crecen (entre +1,8 % en Upper East Side South y +4,2 % en East Village) y seis caen (entre −1,2 % en Penn Station/Madison Sq West y −13,7 % en JFK Airport). JFK Airport lidera con 146.811 viajes (−13,7 %). Respecto de agosto 2025 entra al top 10 East Chelsea y sale LaGuardia Airport. En los aeropuertos, JFK (puesto 1 del top) cae −13,7 % y LaGuardia (fuera del top) cae −9,7 %: los aeropuertos van peor que el total de la ciudad (−5,3 %). La concentración casi no cambia: el top 10 reúne el 33,6 % de los pickups (33,5 % en 2025). Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (30.287 → 13.805), aunque sobre una base chica, contra −5,3 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,67 en 2026 y US$ 31,33 en 2025. Es una hora de poco volumen (31.232 viajes, contra 204.532 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,1 % de sus viajes toca JFK o LaGuardia (contra 9,0 % en todo el mes) y la distancia media es de 5,79 millas (contra 3,71). El ingreso por viaje de esa hora sube un 7,5 % aunque la distancia media baja (de 6,08 a 5,79 millas): lo explican las tarifas y recargos de 2026.

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

**Interpretación:** El 77,12 % de los viajes de agosto 2026 pagó cbd_congestion_fee (2.439.807 de 3.163.698, siempre US$ 0,75). Las cinco zonas con mayor proporción (West Village, Little Italy/NoLiTa, East Village, Greenwich Village South y Penn Station/Madison Sq West, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En agosto 2025 lo pagaba el 73,80 % de los viajes: la proporción sube +3,3 pp. La regla R10 marcó 9.520 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 25,00 % de la tarifa en 2026 frente a 25,04 % en 2025 (22,0 % y 21,2 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 24,3 % al 26,5 % de los viajes (652.377 → 838.107 con tarifa > 0) y cuya propina se mantiene en torno al 1,4 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 25,3 % al 27,8 % de las filas leídas. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 10,5 % (319.485 → 285.907) mientras el total de la ciudad baja un 5,3 %, así que su peso cae del 9,6 % al 9,0 % de los viajes. Por aeropuerto, JFK cae −12,6 % y LaGuardia cae −7,1 %. La tarifa promedio baja de US$ 55,94 a US$ 54,39 (−2,8 %), y la mediana baja de US$ 54,80 a US$ 50,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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

**Interpretación:**

- Agosto 2026 tuvo 3.163.698 viajes válidos contra 3.339.362 en agosto 2025: −175.664 viajes (−5,26 %). La recaudación total (total_amount) crece un 2,9 %, de US$ 92,7 M a US$ 95,4 M.
- Parte de la caída es de calendario: agosto 2026 tuvo 5 lunes (días flojos), y agosto 2025, 5 viernes. Con el calendario de 2025 la variación sería −4,8 %. Por día de la semana la variación va de −12 % a +2 %: el cambio no es parejo.
- La tarifa promedio sube un 10,59 % (de US$ 19,09 a US$ 21,11). La mediana pasa de US$ 13,50 a US$ 15,60 (+15,6 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de agosto 2026 hay más viajes Flex Fare, que son más caros (US$ 24,89 contra US$ 19,74 del resto) y pasan del 24 % al 27 % de los viajes, menos viajes a aeropuertos (del 9,6 % al 9,0 %) y menos viajes de más de 10 millas (del 9,2 % al 8,1 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 3,5 % (de US$ 20,46 a US$ 19,74). El viaje promedio es más corto: 3,71 contra 3,83 millas.
- Calidad: la cuarentena baja del 6,57 % al 5,19 % de las filas leídas (173.018 filas en agosto 2026 y 234.729 en agosto 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,57 % contra 2,95 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,29 % contra 1,34 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en agosto 2026 (−5,3 % de viajes, +2,9 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,7 %), Times Sq/Theatre District (−9,1 %) y LaGuardia Airport (−9,7 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 77,1 % de los viajes de agosto 2026, contra 73,8 % en agosto 2025.
- El viaje promedio es más corto (3,71 contra 3,83 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 13,50 → US$ 15,60). La propina con tarjeta no se mueve (25,0 % → 25,0 %).
- Hay 80 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 950,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (agosto 2026: columna nueva ignorada: request_source). La cuarentena es del 5,19 % y del 6,57 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-08 INGEST_MODE=direct WAREHOUSE=duckdb`.
