# Resultados: marzo 2025 vs marzo 2024

> En marzo 2025 los taxis amarillos hicieron 3.955.206 viajes válidos, +14,5 % que en marzo 2024 (3.453.501), con una recaudación de US$ 107,4 M (+12,1 %).

| | |
|---|---|
| Comando | `make all MES=2025-03 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-03.parquet` y `yellow_tripdata_2024-03.parquet` |
| Corrida | `20261118T045104Z-e04fa7`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=03/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-03 | `yellow_tripdata_2025-03.parquet` | 4.145.257 | 4.145.257 | 3.955.206 | 190.051 | 4,58 % | 879.350 (21,21 %) | sí |
| 2024-03 | `yellow_tripdata_2024-03.parquet` | 3.582.628 | 3.582.628 | 3.453.501 | 129.127 | 3,60 % | 421.321 (11,76 %) | sí |

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

- La cuarentena sube del 3,60 % al 4,58 % de las filas leídas (190.051 filas en marzo 2025 y 129.127 en marzo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,51 % contra 2,44 %) y R04 (total cobrado faltante o negativo: 1,66 % contra 1,24 %).
- La regla que más cambia es R02 (dropoff sin fecha, anterior o igual al pickup): +0,51 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 879.350 filas aceptadas de marzo 2025 (21,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 22,7 %, contra 13,0 % en marzo 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de marzo 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de marzo 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +1,3 % en Lincoln Square East y +19,1 % en East Village) y una cae (JFK Airport −0,8 %). Midtown Center lidera con 175.034 viajes (+10,1 %). Respecto de marzo 2024 entran al top 10 Union Sq y East Village y salen LaGuardia Airport y Murray Hill. En los aeropuertos, JFK (puesto 3 del top) cae −0,8 % y LaGuardia (fuera del top) cae −1,2 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 34,1 % de los pickups, frente al 36,8 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (9.568 → 32.333), aunque sobre una base chica, contra +14,5 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,56 en 2025 y US$ 35,57 en 2024. Es una hora de poco volumen (31.994 viajes, contra 272.709 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,2 % de sus viajes toca JFK o LaGuardia (contra 8,0 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,33). En 2025 los viajes de aeropuerto son menos (del 21,9 % al 18,2 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 5,7 %.

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

**Interpretación:** El 74,25 % de los viajes de marzo 2025 pagó cbd_congestion_fee (2.936.806 de 3.955.206, un cobro medio de US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village North, West Village, Little Italy/NoLiTa y Greenwich Village South, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En marzo 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 47.166 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina sube: 26,10 % de la tarifa en 2025 frente a 25,18 % en 2024 (22,6 % y 22,4 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,0 % al 21,6 % de los viajes (364.912 → 725.934 con tarifa > 0) y cuya propina cae del 3,40 % al 1,97 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 13,0 % al 22,7 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,6 % al 67,3 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 0,6 % (320.254 → 318.287) mientras el total de la ciudad sube un 14,5 %, así que su peso cae del 9,3 % al 8,0 % de los viajes. Por aeropuerto, JFK cae −0,9 % y LaGuardia cae −0,5 %. La tarifa promedio baja de US$ 55,70 a US$ 55,29 (−0,7 %), y la mediana baja de US$ 54,80 a US$ 54,10. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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

**Interpretación:**

- Marzo 2025 tuvo 3.955.206 viajes válidos contra 3.453.501 en marzo 2024: +501.705 viajes (+14,53 %). La recaudación total (total_amount) crece un 12,1 %, de US$ 95,8 M a US$ 107,4 M.
- El calendario juega en contra de marzo 2025: marzo 2025 tuvo 5 lunes (días flojos), y marzo 2024, 5 viernes (días fuertes). Con el calendario de 2024 la variación sería +15,3 %. Todos los días de la semana crecen (por día), entre +9 % y +24 %, así que el aumento es real.
- La tarifa promedio baja un 3,47 % (de US$ 19,06 a US$ 18,40). La mediana no cambia (US$ 13,50): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de marzo 2025 hay más viajes Flex Fare, que son más baratos (US$ 17,19 contra US$ 18,73 del resto) y pasan del 11 % al 22 % de los viajes, menos viajes a aeropuertos (del 9,3 % al 8,0 %) y menos viajes de más de 10 millas (del 7,7 % al 7,1 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,0 % (de US$ 19,11 a US$ 18,73).
- Calidad: la cuarentena sube del 3,60 % al 4,58 % de las filas leídas (190.051 filas en marzo 2025 y 129.127 en marzo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,51 % contra 2,44 %) y R04 (total cobrado faltante o negativo: 1,66 % contra 1,24 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en marzo 2025 (+14,5 % de viajes, +12,1 % de recaudación). Las zonas que más suman viajes son East Village (+19,1 %), Penn Station/Madison Sq West (+14,4 %) y Midtown Center (+10,1 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 74,3 % de los viajes de marzo 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +25,6 %, Greenwich Village North +11,8 % y West Village +12,4 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es igual de largo (3,33 contra 3,36 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 13,50, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta sube (25,2 % → 26,1 %).
- Hay 29 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 999,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (marzo 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,58 % y del 3,60 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-03 INGEST_MODE=direct WAREHOUSE=duckdb`.
