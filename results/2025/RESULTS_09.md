# Resultados: septiembre 2025 vs septiembre 2024

> En septiembre 2025 los taxis amarillos hicieron 3.996.265 viajes válidos, +14,2 % que en septiembre 2024 (3.498.989), con una recaudación de US$ 115,2 M (+12,1 %).

| | |
|---|---|
| Comando | `make all MES=2025-09 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-09.parquet` y `yellow_tripdata_2024-09.parquet` |
| Corrida | `20261118T045117Z-823196`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=09/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-09 | `yellow_tripdata_2025-09.parquet` | 4.251.015 | 4.251.015 | 3.996.265 | 254.750 | 5,99 % | 1.010.489 (23,77 %) | sí |
| 2024-09 | `yellow_tripdata_2024-09.parquet` | 3.633.030 | 3.633.030 | 3.498.989 | 134.041 | 3,69 % | 478.197 (13,16 %) | sí |

| regla | severidad | qué controla | 2025-09 | 2024-09 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 49 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 57.179 (1,35 %) | 1.161 (0,03 %) | +1,31 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 124.697 (2,93 %) | 81.288 (2,24 %) | +0,70 pp |
| R04 | reject | Total cobrado faltante o negativo. | 78.492 (1,85 %) | 56.109 (1,54 %) | +0,30 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.089.381 (25,63 %) | 514.077 (14,15 %) | +11,48 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 257.250 (6,05 %) | 77.288 (2,13 %) | +3,92 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.216 (0,03 %) | 1.199 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 52.097 (1,23 %) | 0 (0,00 %) | +1,23 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,69 % al 5,99 % de las filas leídas (254.750 filas en septiembre 2025 y 134.041 en septiembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,93 % contra 2,24 %) y R04 (total cobrado faltante o negativo: 1,85 % contra 1,54 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,31 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 1.010.489 filas aceptadas de septiembre 2025 (23,8 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 25,6 %, contra 14,2 % en septiembre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de septiembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de septiembre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 178.552 | 162.003 | 16.549 | 10,22 |
| Queens | JFK Airport | 169.419 | 176.441 | -7.022 | -3,98 |
| Manhattan | Midtown Center | 159.404 | 149.535 | 9.869 | 6,60 |
| Manhattan | Upper East Side North | 154.352 | 145.676 | 8.676 | 5,96 |
| Manhattan | Penn Station/Madison Sq West | 129.298 | 116.953 | 12.345 | 10,56 |
| Manhattan | Midtown East | 122.012 | 114.097 | 7.915 | 6,94 |
| Manhattan | Times Sq/Theatre District | 114.854 | 109.245 | 5.609 | 5,13 |
| Manhattan | Union Sq | 107.000 | 97.561 | 9.439 | 9,67 |
| Manhattan | East Chelsea | 106.711 | 101.167 | 5.544 | 5,48 |
| Manhattan | Murray Hill | 106.497 | 98.526 | 7.971 | 8,09 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +5,1 % en Times Sq/Theatre District y +10,6 % en Penn Station/Madison Sq West) y una cae (JFK Airport −4,0 %). Upper East Side South lidera con 178.552 viajes (+10,2 %) y desplaza a JFK Airport, que encabezaba septiembre 2024. Respecto de septiembre 2024 entran al top 10 Union Sq y Murray Hill y salen LaGuardia Airport y Lincoln Square East. En los aeropuertos, JFK (puesto 2 del top) cae −4,0 % y LaGuardia (fuera del top) cae −2,9 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 33,7 % de los pickups, frente al 36,8 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (10.842 → 29.050), aunque sobre una base chica, contra +14,2 % del total.

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
| 2025 | 9 | 16 | 222.524 | 33,99 |
| 2024 | 9 | 5 | 21.797 | 36,91 |

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 16:00 en 2025 (US$ 33,99) y las 5:00 en 2024 (US$ 36,91). Además es una hora de mucho movimiento (222.524 viajes; la hora pico es las 18:00 con 260.300). Gana porque a esa hora pesan los viajes largos: el 11,3 % de sus viajes toca JFK o LaGuardia (contra 8,4 % en todo el mes).

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
| ALL ZONES |  | 3.996.265 | 2.957.534 | 74,01 |
| SoHo | Manhattan | 36.110 | 36.038 | 99,80 |
| Greenwich Village South | Manhattan | 58.581 | 58.456 | 99,79 |
| West Village | Manhattan | 88.340 | 88.098 | 99,73 |
| Greenwich Village North | Manhattan | 55.884 | 55.708 | 99,69 |
| Midtown North | Manhattan | 94.344 | 94.023 | 99,66 |

**Interpretación:** El 74,01 % de los viajes de septiembre 2025 pagó cbd_congestion_fee (2.957.534 de 3.996.265, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Greenwich Village North y Midtown North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En septiembre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 52.097 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 9 | 0 | Flex Fare | 827.190 | 1,44 | 1,49 |
| 2025 | 9 | 1 | Credit card | 2.605.862 | 25,82 | 21,39 |
| 2025 | 9 | 2 | Cash | 338.108 | 0,00 | 0,00 |
| 2025 | 9 | 3 | No charge | 14.000 | 0,08 | 0,03 |
| 2025 | 9 | 4 | Dispute | 52.082 | 0,05 | 0,04 |
| 2024 | 9 | 0 | Flex Fare | 430.353 | 2,43 | 2,66 |
| 2024 | 9 | 1 | Credit card | 2.580.440 | 24,37 | 21,72 |
| 2024 | 9 | 2 | Cash | 422.242 | 0,00 | 0,00 |
| 2024 | 9 | 3 | No charge | 13.409 | 0,11 | 0,04 |
| 2024 | 9 | 4 | Dispute | 36.027 | 0,08 | 0,06 |

**Interpretación:** Con tarjeta de crédito la propina sube: 25,82 % de la tarifa en 2025 frente a 24,37 % en 2024 (21,4 % y 21,7 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 12,8 % al 24,7 % de los viajes (430.353 → 827.190 con tarifa > 0) y cuya propina cae del 2,43 % al 1,44 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 14,2 % al 25,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 73,7 % al 65,2 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 9 | 336.219 | 58,25 | 197.728 | 141.541 |
| 2024 | 9 | 353.323 | 57,52 | 208.645 | 147.694 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 4,8 % (353.323 → 336.219) mientras el total de la ciudad sube un 14,2 %, así que su peso cae del 10,1 % al 8,4 % de los viajes. Por aeropuerto, JFK cae −5,2 % y LaGuardia cae −4,2 %. La tarifa promedio sube de US$ 57,52 a US$ 58,25 (+1,3 %), pero esa suba no es real: la produce un solo viaje de 2025 con fare_amount = US$ 323.800,27 (de JFK Airport a Midtown South, 11,8 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 57,50 a US$ 57,26 (−0,4 %), y la mediana baja de US$ 60,40 a US$ 58,30. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.996.265 | 3.498.989 | 497.276 | 14,21 | 19,99 | 20,54 | -2,70 |

**Interpretación:**

- Septiembre 2025 tuvo 3.996.265 viajes válidos contra 3.498.989 en septiembre 2024: +497.276 viajes (+14,21 %). La recaudación total (total_amount) crece un 12,1 %, de US$ 102,7 M a US$ 115,2 M.
- El calendario casi no influye: septiembre 2025 tuvo 5 martes (días flojos), y septiembre 2024, 5 domingos (días flojos). Todos los días de la semana crecen (por día), entre +9 % y +23 %, así que el aumento es real.
- La tarifa promedio baja un 2,70 % (de US$ 20,54 a US$ 19,99); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 323.800) la baja es del 3,1 % (de US$ 20,54 a US$ 19,90). La mediana pasa de US$ 14,76 a US$ 14,90 (+0,9 %).
- En la mezcla de septiembre 2025 hay más viajes Flex Fare, que son más baratos (US$ 17,64 contra US$ 20,65 del resto) y pasan del 13 % al 25 % de los viajes, menos viajes a aeropuertos (del 10,1 % al 8,4 %) y menos viajes de más de 10 millas (del 8,6 % al 8,3 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,70 a US$ 20,65). El viaje promedio es más largo: 3,63 contra 3,53 millas.
- Calidad: la cuarentena sube del 3,69 % al 5,99 % de las filas leídas (254.750 filas en septiembre 2025 y 134.041 en septiembre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,93 % contra 2,24 %) y R04 (total cobrado faltante o negativo: 1,85 % contra 1,54 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en septiembre 2025 (+14,2 % de viajes, +12,1 % de recaudación). Las zonas que más suman viajes son East Village (+24,0 %), Upper East Side South (+10,2 %) y West Chelsea/Hudson Yards (+22,5 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 74,0 % de los viajes de septiembre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +11,4 %, Greenwich Village South +9,1 % y West Village +4,4 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,63 contra 3,53 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,76 → US$ 14,90). La propina con tarjeta sube (24,4 % → 25,8 %).
- Los promedios son frágiles: 51 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 323.800,27, en 2025) alcanzan para mover la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (septiembre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 5,99 % y del 3,69 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-09 INGEST_MODE=direct WAREHOUSE=duckdb`.
