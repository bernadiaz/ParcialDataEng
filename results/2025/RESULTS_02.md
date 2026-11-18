# Resultados: febrero 2025 vs febrero 2024

> En febrero 2025 los taxis amarillos hicieron 3.421.132 viajes válidos, +17,7 % que en febrero 2024 (2.905.437), con una recaudación de US$ 88,5 M (+12,1 %).

| | |
|---|---|
| Comando | `make all MES=2025-02 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-02.parquet` y `yellow_tripdata_2024-02.parquet` |
| Corrida | `20261118T045102Z-76c2cd`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=02/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-02 | `yellow_tripdata_2025-02.parquet` | 3.577.543 | 3.577.543 | 3.421.132 | 156.411 | 4,37 % | 767.302 (21,45 %) | sí |
| 2024-02 | `yellow_tripdata_2024-02.parquet` | 3.007.526 | 3.007.526 | 2.905.437 | 102.089 | 3,39 % | 189.142 (6,29 %) | sí |

| regla | severidad | qué controla | 2025-02 | 2024-02 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 31 (0,00 %) | 15 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 5.164 (0,14 %) | 803 (0,03 %) | +0,12 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 99.943 (2,79 %) | 68.296 (2,27 %) | +0,52 pp |
| R04 | reject | Total cobrado faltante o negativo. | 55.179 (1,54 %) | 36.080 (1,20 %) | +0,34 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 828.688 (23,16 %) | 219.704 (7,31 %) | +15,86 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 1 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 186.623 (5,22 %) | 44.366 (1,48 %) | +3,74 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 841 (0,02 %) | 953 (0,03 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 37.238 (1,04 %) | 0 (0,00 %) | +1,04 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,39 % al 4,37 % de las filas leídas (156.411 filas en febrero 2025 y 102.089 en febrero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,79 % contra 2,27 %) y R04 (total cobrado faltante o negativo: 1,54 % contra 1,20 %).
- Las reglas de advertencia no sacan filas: 767.302 filas aceptadas de febrero 2025 (21,4 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 23,2 %, contra 7,3 % en febrero 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de febrero 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de febrero 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Midtown Center | 155.533 | 143.505 | 12.028 | 8,38 |
| Manhattan | Upper East Side South | 152.770 | 138.088 | 14.682 | 10,63 |
| Manhattan | Upper East Side North | 143.712 | 131.205 | 12.507 | 9,53 |
| Queens | JFK Airport | 115.233 | 120.600 | -5.367 | -4,45 |
| Manhattan | Times Sq/Theatre District | 109.839 | 98.729 | 11.110 | 11,25 |
| Manhattan | Midtown East | 109.808 | 103.364 | 6.444 | 6,23 |
| Manhattan | Penn Station/Madison Sq West | 109.148 | 97.913 | 11.235 | 11,47 |
| Manhattan | Lincoln Square East | 101.271 | 94.882 | 6.389 | 6,73 |
| Manhattan | Union Sq | 98.966 | 82.227 | 16.739 | 20,36 |
| Manhattan | East Village | 93.197 | 72.646 | 20.551 | 28,29 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +6,2 % en Midtown East y +28,3 % en East Village) y una cae (JFK Airport −4,5 %). Midtown Center lidera con 155.533 viajes (+8,4 %). Respecto de febrero 2024 entran al top 10 Union Sq y East Village y salen Upper West Side South y Midtown North. En los aeropuertos, JFK (puesto 4 del top) cae −4,5 % y LaGuardia (fuera del top) cae −4,2 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 34,8 % de los pickups, frente al 38,0 % de 2024. Fuera de Manhattan, Brooklyn más que triplica sus pickups (24.881 → 90.071), aunque sobre una base chica, contra +17,7 % del total.

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
| 2025 | 2 | 5 | 23.365 | 32,29 |
| 2024 | 2 | 5 | 16.648 | 37,74 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 32,29 en 2025 y US$ 37,74 en 2024. Es una hora de poco volumen (23.365 viajes, contra 245.997 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,2 % de sus viajes toca JFK o LaGuardia (contra 7,1 % en todo el mes) y la distancia media es de 5,57 millas (contra 3,12). En 2025 los viajes de aeropuerto son menos (del 26,3 % al 18,2 % de los viajes de las 5:00) y la distancia media baja (de 6,21 a 5,57 millas), por eso el ingreso por viaje cae un 14,4 %.

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
| ALL ZONES |  | 3.421.132 | 2.534.752 | 74,09 |
| SoHo | Manhattan | 30.799 | 30.732 | 99,78 |
| Greenwich Village South | Manhattan | 56.528 | 56.401 | 99,78 |
| West Village | Manhattan | 83.745 | 83.537 | 99,75 |
| Union Sq | Manhattan | 98.966 | 98.718 | 99,75 |
| Midtown Center | Manhattan | 155.533 | 155.111 | 99,73 |

**Interpretación:** El 74,09 % de los viajes de febrero 2025 pagó cbd_congestion_fee (2.534.752 de 3.421.132, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Union Sq y Midtown Center, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En febrero 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 37.238 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 2 | 0 | Flex Fare | 628.164 | 1,90 | 2,00 |
| 2025 | 2 | 1 | Credit card | 2.312.981 | 26,35 | 22,87 |
| 2025 | 2 | 2 | Cash | 317.947 | 0,00 | 0,00 |
| 2025 | 2 | 3 | No charge | 11.348 | 0,43 | 0,12 |
| 2025 | 2 | 4 | Dispute | 35.028 | 0,08 | 0,09 |
| 2024 | 2 | 0 | Flex Fare | 148.816 | 6,73 | 6,90 |
| 2024 | 2 | 1 | Credit card | 2.321.720 | 25,35 | 22,59 |
| 2024 | 2 | 2 | Cash | 396.447 | 0,00 | 0,00 |
| 2024 | 2 | 3 | No charge | 10.263 | 0,05 | 0,06 |
| 2024 | 2 | 4 | Dispute | 23.238 | 0,05 | 0,09 |

**Interpretación:** Con tarjeta de crédito la propina sube: 26,35 % de la tarifa en 2025 frente a 25,35 % en 2024 (22,9 % y 22,6 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 5,3 % al 21,7 % de los viajes (148.816 → 628.164 con tarifa > 0) y cuya propina cae del 6,73 % al 1,90 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 7,3 % al 23,2 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 79,9 % al 67,6 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 2 | 242.974 | 54,31 | 135.405 | 109.694 |
| 2024 | 2 | 257.856 | 54,77 | 143.729 | 116.530 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 5,8 % (257.856 → 242.974) mientras el total de la ciudad sube un 17,7 %, así que su peso cae del 8,9 % al 7,1 % de los viajes. Por aeropuerto, JFK cae −5,8 % y LaGuardia cae −5,9 %. La tarifa promedio baja de US$ 54,77 a US$ 54,31 (−0,8 %), y la mediana baja de US$ 52,70 a US$ 51,30. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.421.132 | 2.905.437 | 515.695 | 17,75 | 17,31 | 18,38 | -5,80 |

**Interpretación:**

- Febrero 2025 tuvo 3.421.132 viajes válidos contra 2.905.437 en febrero 2024: +515.695 viajes (+17,75 %). La recaudación total (total_amount) crece un 12,1 %, de US$ 79,0 M a US$ 88,5 M.
- El calendario juega en contra de febrero 2025: febrero 2024 tuvo 5 jueves (días fuertes) y febrero 2025 no (28 contra 29 días). Con el calendario de 2024 la variación sería +22,3 %. Todos los días de la semana crecen (por día), entre +14 % y +33 %, así que el aumento es real.
- La tarifa promedio baja un 5,80 % (de US$ 18,38 a US$ 17,31). La mediana no cambia (US$ 12,80): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de febrero 2025 hay más viajes Flex Fare, que son más baratos (US$ 15,40 contra US$ 17,79 del resto) y pasan del 5 % al 22 % de los viajes, menos viajes a aeropuertos (del 8,9 % al 7,1 %) y menos viajes de más de 10 millas (del 7,3 % al 6,1 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 3,0 % (de US$ 18,34 a US$ 17,79). El viaje promedio es más corto: 3,12 contra 3,22 millas.
- Calidad: la cuarentena sube del 3,39 % al 4,37 % de las filas leídas (156.411 filas en febrero 2025 y 102.089 en febrero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,79 % contra 2,27 %) y R04 (total cobrado faltante o negativo: 1,54 % contra 1,20 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en febrero 2025 (+17,7 % de viajes, +12,1 % de recaudación). Las zonas que más suman viajes son East Village (+28,3 %), Union Sq (+20,4 %) y West Chelsea/Hudson Yards (+31,2 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 74,1 % de los viajes de febrero 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +30,3 %, Greenwich Village South +26,9 % y West Village +16,6 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más corto (3,12 contra 3,22 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 12,80, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta sube (25,4 % → 26,4 %).
- Hay 30 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 132.531,36, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (febrero 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,37 % y del 3,39 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-02 INGEST_MODE=direct WAREHOUSE=duckdb`.
