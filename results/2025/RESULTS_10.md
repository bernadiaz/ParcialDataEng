# Resultados: octubre 2025 vs octubre 2024

> En octubre 2025 los taxis amarillos hicieron 4.135.934 viajes válidos, +12,0 % que en octubre 2024 (3.694.253), con una recaudación de US$ 116,6 M (+7,8 %).

| | |
|---|---|
| Comando | `make all MES=2025-10 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-10.parquet` y `yellow_tripdata_2024-10.parquet` |
| Corrida | `20261118T045120Z-fa51c9`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=10/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-10 | `yellow_tripdata_2025-10.parquet` | 4.428.699 | 4.428.699 | 4.135.934 | 292.765 | 6,61 % | 900.005 (20,32 %) | sí |
| 2024-10 | `yellow_tripdata_2024-10.parquet` | 3.833.771 | 3.833.771 | 3.694.253 | 139.518 | 3,64 % | 395.875 (10,33 %) | sí |

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

- La cuarentena sube del 3,64 % al 6,61 % de las filas leídas (292.765 filas en octubre 2025 y 139.518 en octubre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,84 % contra 2,13 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,60 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +1,51 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 900.005 filas aceptadas de octubre 2025 (20,3 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 22,9 %, contra 11,2 % en octubre 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de octubre 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de octubre 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +0,9 % en LaGuardia Airport y +8,7 % en Penn Station/Madison Sq West) y una cae (JFK Airport −3,5 %). Upper East Side South lidera con 194.841 viajes (+4,5 %). Respecto de octubre 2024 entra al top 10 Union Sq y sale Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −3,5 % y LaGuardia (puesto 9 del top) crece +0,9 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 35,2 % de los pickups, frente al 38,4 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (11.308 → 30.719), aunque sobre una base chica, contra +12,0 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje cambia: las 16:00 en 2025 (US$ 32,29) y las 5:00 en 2024 (US$ 37,10). Además es una hora de mucho movimiento (235.339 viajes; la hora pico es las 18:00 con 276.793). No la explican los aeropuertos ni la distancia, que a esa hora son parecidos al resto del día: pesan los recargos y peajes de esos viajes.

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

**Interpretación:** El 73,82 % de los viajes de octubre 2025 pagó cbd_congestion_fee (3.053.045 de 4.135.934, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Midtown North y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En octubre 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 45.667 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 24,91 % de la tarifa en 2025 frente a 24,73 % en 2024 (21,5 % y 22,0 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 9,7 % al 21,2 % de los viajes (345.123 → 682.354 con tarifa > 0) y cuya propina cae del 3,27 % al 1,77 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 11,2 % al 22,9 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 76,6 % al 68,5 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 3,9 % (373.321 → 358.652) mientras el total de la ciudad sube un 12,0 %, así que su peso cae del 10,1 % al 8,7 % de los viajes. Por aeropuerto, JFK cae −5,5 % y LaGuardia cae −1,9 %. La tarifa promedio se mantiene (US$ 57,15 → US$ 57,04), y la mediana baja de US$ 59,00 a US$ 57,60. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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

**Interpretación:**

- Octubre 2025 tuvo 4.135.934 viajes válidos contra 3.694.253 en octubre 2024: +441.681 viajes (+11,96 %). La recaudación total (total_amount) crece un 7,8 %, de US$ 108,2 M a US$ 116,6 M.
- Parte del salto es de calendario: octubre 2025 tuvo 5 viernes (días fuertes), y octubre 2024, 5 martes (días flojos). Con el calendario de 2024 la variación sería +11,5 %. Todos los días de la semana crecen (por día), entre +7 % y +17 %, así que el aumento es real.
- La tarifa promedio baja un 5,50 % (de US$ 20,29 a US$ 19,17). La mediana no cambia (US$ 14,20): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de octubre 2025 hay más viajes Flex Fare, que son más baratos (US$ 13,98 contra US$ 20,56 del resto) y pasan del 10 % al 21 % de los viajes, menos viajes a aeropuertos (del 10,1 % al 8,7 %) y menos viajes de más de 10 millas (del 8,5 % al 8,2 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,40 a US$ 20,56). El viaje promedio es más largo: 3,58 contra 3,48 millas.
- Calidad: la cuarentena sube del 3,64 % al 6,61 % de las filas leídas (292.765 filas en octubre 2025 y 139.518 en octubre 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,84 % contra 2,13 %) y R04 (total cobrado faltante o negativo: 2,46 % contra 1,60 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en octubre 2025 (+12,0 % de viajes, +7,8 % de recaudación). Las zonas que más suman viajes son East Village (+28,1 %), West Chelsea/Hudson Yards (+21,5 %) y Lower East Side (+33,7 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 73,8 % de los viajes de octubre 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +9,3 %, Greenwich Village South +10,1 % y West Village +6,0 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,58 contra 3,48 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 14,20, así que el cambio viene de la mezcla de viajes (más Flex Fare y menos aeropuertos). La propina con tarjeta no se mueve (24,7 % → 24,9 %).
- Hay 40 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 800,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (octubre 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,61 % y del 3,64 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-10 INGEST_MODE=direct WAREHOUSE=duckdb`.
