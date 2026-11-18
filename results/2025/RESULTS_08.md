# Resultados: agosto 2025 vs agosto 2024

> En agosto 2025 los taxis amarillos hicieron 3.339.362 viajes válidos, +16,3 % que en agosto 2024 (2.871.735), con una recaudación de US$ 92,7 M (+10,7 %).

| | |
|---|---|
| Comando | `make all MES=2025-08 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-08.parquet` y `yellow_tripdata_2024-08.parquet` |
| Corrida | `20261118T045115Z-d471ae`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=08/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-08 | `yellow_tripdata_2025-08.parquet` | 3.574.091 | 3.574.091 | 3.339.362 | 234.729 | 6,57 % | 831.289 (23,26 %) | sí |
| 2024-08 | `yellow_tripdata_2024-08.parquet` | 2.979.183 | 2.979.183 | 2.871.735 | 107.448 | 3,61 % | 271.502 (9,11 %) | sí |

| regla | severidad | qué controla | 2025-08 | 2024-08 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 17 (0,00 %) | 51 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 47.833 (1,34 %) | 1.018 (0,03 %) | +1,30 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 105.429 (2,95 %) | 57.569 (1,93 %) | +1,02 pp |
| R04 | reject | Total cobrado faltante o negativo. | 87.940 (2,46 %) | 52.940 (1,78 %) | +0,68 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 903.506 (25,28 %) | 284.934 (9,56 %) | +15,72 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 265.314 (7,42 %) | 62.244 (2,09 %) | +5,33 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.070 (0,03 %) | 1.047 (0,04 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 51.507 (1,44 %) | 0 (0,00 %) | +1,44 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,61 % al 6,57 % de las filas leídas (234.729 filas en agosto 2025 y 107.448 en agosto 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,95 % contra 1,93 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,78 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,30 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 831.289 filas aceptadas de agosto 2025 (23,3 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 25,3 %, contra 9,6 % en agosto 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de agosto 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de agosto 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Queens | JFK Airport | 170.088 | 171.407 | -1.319 | -0,77 |
| Manhattan | Midtown Center | 137.058 | 136.599 | 459 | 0,34 |
| Manhattan | Upper East Side South | 120.393 | 116.632 | 3.761 | 3,22 |
| Manhattan | Penn Station/Madison Sq West | 113.281 | 102.564 | 10.717 | 10,45 |
| Manhattan | Midtown East | 102.370 | 102.351 | 19 | 0,02 |
| Manhattan | Times Sq/Theatre District | 101.953 | 98.935 | 3.018 | 3,05 |
| Manhattan | Upper East Side North | 97.952 | 98.841 | -889 | -0,90 |
| Queens | LaGuardia Airport | 94.403 | 99.475 | -5.072 | -5,10 |
| Manhattan | Murray Hill | 92.827 | 86.121 | 6.706 | 7,79 |
| Manhattan | East Village | 87.277 | 63.753 | 23.524 | 36,90 |

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, cinco crecen (entre +3,1 % en Times Sq/Theatre District y +36,9 % en East Village), tres caen (LaGuardia Airport −5,1 %, Upper East Side North −0,9 %, JFK Airport −0,8 %) y dos se mantienen. JFK Airport lidera con 170.088 viajes (−0,8 %). Respecto de agosto 2024 entra al top 10 East Village y sale East Chelsea. En los aeropuertos, JFK (puesto 1 del top) cae −0,8 % y LaGuardia (puesto 8 del top) cae −5,1 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 33,5 % de los pickups, frente al 38,1 % de 2024. Fuera de Manhattan, Brooklyn más que triplica sus pickups (42.955 → 156.423), contra +16,3 % del total.

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
| 2025 | 8 | 5 | 28.811 | 31,33 |
| 2024 | 8 | 5 | 19.473 | 36,80 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 31,33 en 2025 y US$ 36,80 en 2024. Es una hora de poco volumen (28.811 viajes, contra 219.584 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 17,2 % de sus viajes toca JFK o LaGuardia (contra 9,6 % en todo el mes) y la distancia media es de 6,08 millas (contra 3,83). En 2025 los viajes de aeropuerto son menos (del 24,5 % al 17,2 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 14,9 %.

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
| ALL ZONES |  | 3.339.362 | 2.464.363 | 73,80 |
| Greenwich Village South | Manhattan | 47.967 | 47.882 | 99,82 |
| West Village | Manhattan | 73.979 | 73.810 | 99,77 |
| SoHo | Manhattan | 28.968 | 28.895 | 99,75 |
| Greenwich Village North | Manhattan | 43.228 | 43.097 | 99,70 |
| East Village | Manhattan | 87.277 | 86.994 | 99,68 |

**Interpretación:** El 73,80 % de los viajes de agosto 2025 pagó cbd_congestion_fee (2.464.363 de 3.339.362, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, West Village, SoHo, Greenwich Village North y East Village, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En agosto 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 51.507 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 8 | 0 | Flex Fare | 652.377 | 1,31 | 1,59 |
| 2025 | 8 | 1 | Credit card | 2.123.062 | 25,04 | 21,22 |
| 2025 | 8 | 2 | Cash | 338.269 | 0,00 | 0,00 |
| 2025 | 8 | 3 | No charge | 14.095 | 0,11 | 0,03 |
| 2025 | 8 | 4 | Dispute | 52.019 | 0,05 | 0,05 |
| 2024 | 8 | 0 | Flex Fare | 238.454 | 3,56 | 3,93 |
| 2024 | 8 | 1 | Credit card | 2.153.085 | 24,73 | 21,40 |
| 2024 | 8 | 2 | Cash | 427.427 | 0,00 | 0,00 |
| 2024 | 8 | 3 | No charge | 13.221 | 0,15 | 0,05 |
| 2024 | 8 | 4 | Dispute | 33.954 | 0,03 | 0,04 |

**Interpretación:** Con tarjeta de crédito la propina sube: 25,04 % de la tarifa en 2025 frente a 24,73 % en 2024 (21,2 % y 21,4 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 8,5 % al 24,3 % de los viajes (238.454 → 652.377 con tarifa > 0) y cuya propina cae del 3,56 % al 1,31 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 9,6 % al 25,3 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 75,0 % al 63,6 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 8 | 319.485 | 55,94 | 196.123 | 126.557 |
| 2024 | 8 | 330.636 | 56,25 | 200.385 | 134.161 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 3,4 % (330.636 → 319.485) mientras el total de la ciudad sube un 16,3 %, así que su peso cae del 11,5 % al 9,6 % de los viajes. Por aeropuerto, JFK cae −2,1 % y LaGuardia cae −5,7 %. La tarifa promedio baja de US$ 56,25 a US$ 55,94 (−0,5 %), y la mediana baja de US$ 55,50 a US$ 54,80. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.339.362 | 2.871.735 | 467.627 | 16,28 | 19,09 | 20,32 | -6,07 |

**Interpretación:**

- Agosto 2025 tuvo 3.339.362 viajes válidos contra 2.871.735 en agosto 2024: +467.627 viajes (+16,28 %). La recaudación total (total_amount) crece un 10,7 %, de US$ 83,8 M a US$ 92,7 M.
- El calendario casi no influye: agosto 2025 tuvo 5 domingos (días flojos), y agosto 2024, 5 jueves (días fuertes). Todos los días de la semana crecen (por día), entre +8 % y +30 %, así que el aumento es real.
- La tarifa promedio baja un 6,07 % (de US$ 20,32 a US$ 19,09). La mediana pasa de US$ 14,15 a US$ 13,50 (−4,6 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de agosto 2025 hay más viajes Flex Fare, que son más baratos (US$ 14,79 contra US$ 20,46 del resto) y pasan del 8 % al 24 % de los viajes, menos viajes a aeropuertos (del 11,5 % al 9,6 %) y menos viajes de más de 10 millas (del 9,6 % al 9,2 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,38 a US$ 20,46). El viaje promedio es más largo: 3,83 contra 3,66 millas.
- Calidad: la cuarentena sube del 3,61 % al 6,57 % de las filas leídas (234.729 filas en agosto 2025 y 107.448 en agosto 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,95 % contra 1,93 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,78 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en agosto 2025 (+16,3 % de viajes, +10,7 % de recaudación). Las zonas que más suman viajes son East Village (+36,9 %), Lower East Side (+41,1 %) y Penn Station/Madison Sq West (+10,4 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 73,8 % de los viajes de agosto 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Greenwich Village South +13,2 %, West Village +10,8 % y SoHo +12,9 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,83 contra 3,66 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,15 → US$ 13,50). La propina con tarjeta sube (24,7 % → 25,0 %).
- Hay 78 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 921,40, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (agosto 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,57 % y del 3,61 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-08 INGEST_MODE=direct WAREHOUSE=duckdb`.
