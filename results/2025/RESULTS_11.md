# Resultados: noviembre 2025 vs noviembre 2024

> En noviembre 2025 los taxis amarillos hicieron 3.892.871 viajes válidos, +10,6 % que en noviembre 2024 (3.519.815), con una recaudación de US$ 104,6 M (+4,3 %).

| | |
|---|---|
| Comando | `make all MES=2025-11 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-11.parquet` y `yellow_tripdata_2024-11.parquet` |
| Corrida | `20261118T045122Z-2a9041`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=11/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-11 | `yellow_tripdata_2025-11.parquet` | 4.181.444 | 4.181.444 | 3.892.871 | 288.573 | 6,90 % | 895.294 (21,41 %) | sí |
| 2024-11 | `yellow_tripdata_2024-11.parquet` | 3.646.369 | 3.646.369 | 3.519.815 | 126.554 | 3,47 % | 376.971 (10,34 %) | sí |

| regla | severidad | qué controla | 2025-11 | 2024-11 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 24 (0,00 %) | 50 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 62.120 (1,49 %) | 1.861 (0,05 %) | +1,43 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 109.643 (2,62 %) | 68.463 (1,88 %) | +0,74 pp |
| R04 | reject | Total cobrado faltante o negativo. | 126.919 (3,04 %) | 60.563 (1,66 %) | +1,37 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.034.682 (24,74 %) | 402.044 (11,03 %) | +13,72 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 399.651 (9,56 %) | 76.015 (2,08 %) | +7,47 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.171 (0,03 %) | 1.023 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 32.145 (0,77 %) | 0 (0,00 %) | +0,77 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,47 % al 6,90 % de las filas leídas (288.573 filas en noviembre 2025 y 126.554 en noviembre 2024). La explican sobre todo R04 (total cobrado faltante o negativo: 3,04 % contra 1,66 %) y R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 1,88 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,43 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 895.294 filas aceptadas de noviembre 2025 (21,4 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 24,7 %, contra 11,0 % en noviembre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de noviembre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de noviembre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 184.875 | 175.996 | 8.879 | 5,05 |
| Manhattan | Midtown Center | 173.173 | 166.724 | 6.449 | 3,87 |
| Manhattan | Upper East Side North | 160.128 | 156.402 | 3.726 | 2,38 |
| Queens | JFK Airport | 153.133 | 151.461 | 1.672 | 1,10 |
| Manhattan | Penn Station/Madison Sq West | 123.805 | 116.190 | 7.615 | 6,55 |
| Manhattan | Midtown East | 121.787 | 117.918 | 3.869 | 3,28 |
| Manhattan | Times Sq/Theatre District | 118.046 | 121.186 | -3.140 | -2,59 |
| Manhattan | Lincoln Square East | 117.674 | 118.171 | -497 | -0,42 |
| Manhattan | Upper West Side South | 103.461 | 101.955 | 1.506 | 1,48 |
| Queens | LaGuardia Airport | 102.446 | 101.695 | 751 | 0,74 |

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, ocho crecen (entre +0,7 % en LaGuardia Airport y +6,6 % en Penn Station/Madison Sq West), una cae (Times Sq/Theatre District −2,6 %) y una se mantiene. Upper East Side South lidera con 184.875 viajes (+5,0 %). Respecto de noviembre 2024 entra al top 10 LaGuardia Airport y sale Midtown North. En los aeropuertos, JFK (puesto 4 del top) crece +1,1 % y LaGuardia (puesto 10 del top) crece +0,7 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 34,9 % de los pickups, frente al 37,8 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (11.603 → 32.483), aunque sobre una base chica, contra +10,6 % del total.

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
| 2025 | 11 | 16 | 232.261 | 30,81 |
| 2024 | 11 | 5 | 24.544 | 37,07 |

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 16:00 en 2025 (US$ 30,81) y las 5:00 en 2024 (US$ 37,07). Además es una hora de mucho movimiento (232.261 viajes; la hora pico es las 18:00 con 254.868). No la explican los aeropuertos ni la distancia, que a esa hora son parecidos al resto del día: pesan los recargos y peajes de esos viajes.

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
| ALL ZONES |  | 3.892.871 | 2.849.734 | 73,20 |
| Greenwich Village South | Manhattan | 57.334 | 57.191 | 99,75 |
| SoHo | Manhattan | 32.389 | 32.305 | 99,74 |
| West Village | Manhattan | 82.974 | 82.681 | 99,65 |
| Little Italy/NoLiTa | Manhattan | 42.518 | 42.355 | 99,62 |
| Midtown North | Manhattan | 102.306 | 101.880 | 99,58 |

**Interpretación:** El 73,20 % de los viajes de noviembre 2025 pagó cbd_congestion_fee (2.849.734 de 3.892.871, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, SoHo, West Village, Little Italy/NoLiTa y Midtown North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En noviembre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 32.145 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 11 | 0 | Flex Fare | 622.969 | 1,92 | 2,70 |
| 2025 | 11 | 1 | Credit card | 2.628.635 | 24,69 | 21,22 |
| 2025 | 11 | 2 | Cash | 346.700 | 0,00 | 0,00 |
| 2025 | 11 | 3 | No charge | 11.045 | 0,00 | 0,00 |
| 2025 | 11 | 4 | Dispute | 33.199 | 0,00 | 0,00 |
| 2024 | 11 | 0 | Flex Fare | 335.693 | 3,32 | 3,61 |
| 2024 | 11 | 1 | Credit card | 2.696.527 | 26,26 | 22,01 |
| 2024 | 11 | 2 | Cash | 425.608 | 0,00 | 0,00 |
| 2024 | 11 | 3 | No charge | 14.203 | 0,06 | 0,02 |
| 2024 | 11 | 4 | Dispute | 36.762 | 0,06 | 0,07 |

**Interpretación:** Con tarjeta de crédito la propina baja: 24,69 % de la tarifa en 2025 frente a 26,26 % en 2024 (21,2 % y 22,0 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 9,8 % al 22,4 % de los viajes (335.693 → 622.969 con tarifa > 0) y cuya propina cae del 3,32 % al 1,92 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 11,0 % al 24,7 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 76,6 % al 67,5 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 11 | 315.604 | 56,50 | 180.138 | 137.865 |
| 2024 | 11 | 321.940 | 56,88 | 182.633 | 141.851 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 2,0 % (321.940 → 315.604) mientras el total de la ciudad sube un 10,6 %, así que su peso cae del 9,1 % al 8,1 % de los viajes. Por aeropuerto, JFK cae −1,4 % y LaGuardia cae −2,8 %. La tarifa promedio baja de US$ 56,88 a US$ 56,50 (−0,7 %), y la mediana baja de US$ 58,30 a US$ 56,20. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.892.871 | 3.519.815 | 373.056 | 10,60 | 18,11 | 19,77 | -8,41 |

**Interpretación:**

- Noviembre 2025 tuvo 3.892.871 viajes válidos contra 3.519.815 en noviembre 2024: +373.056 viajes (+10,60 %). La recaudación total (total_amount) crece un 4,3 %, de US$ 100,3 M a US$ 104,6 M.
- El calendario casi no influye: noviembre 2025 tuvo 5 domingos (días flojos), y noviembre 2024, 5 viernes. Todos los días de la semana crecen (por día), entre +4 % y +17 %, así que el aumento es real.
- La tarifa promedio baja un 8,41 % (de US$ 19,77 a US$ 18,11); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 335.544) la baja es del 8,0 % (de US$ 19,67 a US$ 18,10). La mediana pasa de US$ 14,20 a US$ 13,50 (−4,9 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de noviembre 2025 hay más viajes Flex Fare, que son más baratos (US$ 10,79 contra US$ 20,22 del resto) y pasan del 10 % al 22 % de los viajes, menos viajes a aeropuertos (del 9,1 % al 8,1 %) y más viajes de más de 10 millas (del 7,7 % al 8,0 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 3,0 % (de US$ 19,63 a US$ 20,22). El viaje promedio es más largo: 3,53 contra 3,34 millas.
- Calidad: la cuarentena sube del 3,47 % al 6,90 % de las filas leídas (288.573 filas en noviembre 2025 y 126.554 en noviembre 2024). La explican sobre todo R04 (total cobrado faltante o negativo: 3,04 % contra 1,66 %) y R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 1,88 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en noviembre 2025 (+10,6 % de viajes, +4,3 % de recaudación). Las zonas que más suman viajes son East Village (+21,0 %), West Chelsea/Hudson Yards (+16,6 %) y Lower East Side (+23,1 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 73,2 % de los viajes de noviembre 2025; en noviembre 2024 todavía no existía, así que no hay comparación directa.
- El viaje promedio es más largo (3,53 contra 3,34 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 13,50). La propina con tarjeta baja (26,3 % → 24,7 %).
- Los promedios son frágiles: 41 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 335.544,44, en 2024) alcanzan para mover la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (noviembre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,90 % y del 3,47 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-11 INGEST_MODE=direct WAREHOUSE=duckdb`.
