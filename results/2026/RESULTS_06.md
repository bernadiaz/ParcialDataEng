# Resultados: junio 2026 vs junio 2025

> En junio 2026 los taxis amarillos hicieron 3.646.879 viajes válidos, −10,0 % que en junio 2025 (4.050.910), con una recaudación de US$ 111,6 M (−3,1 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-06 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-06.parquet` y `yellow_tripdata_2025-06.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-06`](http://localhost:8090/superset/dashboard/respaldo-local-2026-06/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T015350Z-fa7da8`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=06/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-06 | `yellow_tripdata_2026-06.parquet` | 3.837.248 | 3.837.248 | 3.646.879 | 190.369 | 4,96 % | 936.142 (24,40 %) | sí |
| 2025-06 | `yellow_tripdata_2025-06.parquet` | 4.322.960 | 4.322.960 | 4.050.910 | 272.050 | 6,29 % | 1.143.555 (26,45 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2026-06 | 2025-06 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 17 (0,00 %) | 20 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 49.807 (1,30 %) | 68.583 (1,59 %) | −0,29 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 128.255 (3,34 %) | 135.160 (3,13 %) | +0,22 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.312 (0,37 %) | 74.257 (1,72 %) | −1,34 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.023.916 (26,68 %) | 1.235.737 (28,59 %) | −1,90 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 18.385 (0,48 %) | 280.005 (6,48 %) | −6,00 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 992 (0,03 %) | 1.522 (0,04 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.424 (0,25 %) | 49.930 (1,15 %) | −0,91 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 6,29 % al 4,96 % de las filas leídas (190.369 filas en junio 2026 y 272.050 en junio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,34 % contra 3,13 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,30 % contra 1,59 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,34 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 936.142 filas aceptadas de junio 2026 (24,4 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 26,7 %, contra 28,6 % en junio 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de junio 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de junio 2025: el archivo coincide con el contrato (mismas columnas y tipos).

**Respaldo en Superset:** [EC.4 Contrato de esquema: novedades de cada archivo][EC.4]

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
| Manhattan | Upper East Side South | 170.750 | 169.806 | 944 | 0,56 |
| Manhattan | Midtown Center | 154.901 | 168.094 | -13.193 | -7,85 |
| Manhattan | Upper East Side North | 149.903 | 147.490 | 2.413 | 1,64 |
| Queens | JFK Airport | 142.206 | 170.532 | -28.326 | -16,61 |
| Manhattan | Midtown East | 114.952 | 122.379 | -7.427 | -6,07 |
| Manhattan | Lincoln Square East | 107.116 | 108.997 | -1.881 | -1,73 |
| Manhattan | Times Sq/Theatre District | 105.994 | 121.466 | -15.472 | -12,74 |
| Manhattan | Penn Station/Madison Sq West | 103.514 | 121.977 | -18.463 | -15,14 |
| Manhattan | Murray Hill | 98.996 | 108.371 | -9.375 | -8,65 |
| Queens | LaGuardia Airport | 97.889 | 108.948 | -11.059 | -10,15 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, dos crecen (entre +0,6 % en Upper East Side South y +1,6 % en Upper East Side North) y ocho caen (entre −1,7 % en Lincoln Square East y −16,6 % en JFK Airport). Upper East Side South lidera con 170.750 viajes (+0,6 %) y desplaza a JFK Airport, que encabezaba junio 2025. En los aeropuertos, JFK (puesto 4 del top) cae −16,6 % y LaGuardia (puesto 10 del top) cae −10,2 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−10,0 %). La demanda se concentra más: el top 10 reúne el 34,2 % de los pickups, frente al 33,3 % de 2025. Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (33.860 → 13.865), aunque sobre una base chica, contra −10,0 % del total.

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1] · [E1.3 Top 10 del mismo mes del año anterior][E1.3] · [E1.4 Concentración y composición del top 10][E1.4] · [E1.5 Pickups en JFK y LaGuardia][E1.5] · [E1.6 Pickups por borough][E1.6]

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
| 2026 | 6 | 5 | 33.068 | 35,27 |
| 2025 | 6 | 5 | 33.295 | 32,56 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 35,27 en 2026 y US$ 32,56 en 2025. Es una hora de poco volumen (33.068 viajes, contra 231.475 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 17,9 % de sus viajes toca JFK o LaGuardia (contra 8,2 % en todo el mes) y la distancia media es de 5,43 millas (contra 3,39). En 2026 los viajes de aeropuerto son más (del 16,1 % al 17,9 % de los viajes de las 5:00), por eso el ingreso por viaje sube un 8,3 %, aunque la distancia media baja (de 5,78 a 5,43 millas). Ojo con el tercer puesto de 2025 (las 14:00, US$ 30,80): es artificial, porque lo infla un viaje con una tarifa de US$ 325.478,05. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 29,40.

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1] · [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5]

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
| ALL ZONES |  | 3.646.879 | 2.707.309 | 74,24 |
| Penn Station/Madison Sq West | Manhattan | 103.514 | 102.830 | 99,34 |
| Midtown East | Manhattan | 114.952 | 113.973 | 99,15 |
| Sutton Place/Turtle Bay North | Manhattan | 60.696 | 60.179 | 99,15 |
| Battery Park | Manhattan | 1.093 | 1.083 | 99,09 |
| Midtown North | Manhattan | 93.796 | 92.881 | 99,02 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 74,24 % de los viajes de junio 2026 pagó cbd_congestion_fee (2.707.309 de 3.646.879, siempre US$ 0,75). Las cinco zonas con mayor proporción (Penn Station/Madison Sq West, Midtown East, Sutton Place/Turtle Bay North, Battery Park y Midtown North, alrededor del 99 %) están todas en Manhattan, dentro de la zona de peaje. En junio 2025 lo pagaba el 73,75 % de los viajes: la proporción sube +0,5 pp. La regla R10 marcó 9.424 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.2 Proporción diaria de viajes con peaje (%)][E3.2] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3] · [E3.5 Regla R10: cobros anómalos del peaje][E3.5]

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
| 2026 | 6 | 0 | Flex Fare | 921.190 | 1,71 | 1,53 |
| 2026 | 6 | 1 | Credit card | 2.367.555 | 26,36 | 23,05 |
| 2026 | 6 | 2 | Cash | 338.611 | 0,00 | 0,00 |
| 2026 | 6 | 3 | No charge | 6.419 | 0,00 | 0,00 |
| 2026 | 6 | 4 | Dispute | 11.058 | 0,01 | 0,01 |
| 2025 | 6 | 0 | Flex Fare | 936.118 | 1,49 | 1,49 |
| 2025 | 6 | 1 | Credit card | 2.517.597 | 25,25 | 22,13 |
| 2025 | 6 | 2 | Cash | 351.739 | 0,00 | 0,00 |
| 2025 | 6 | 3 | No charge | 14.062 | 0,07 | 0,11 |
| 2025 | 6 | 4 | Dispute | 48.613 | 0,03 | 0,02 |
| 2025 | 6 | 5 | Unknown | 1 | 0,00 | 0,00 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina sube: 26,36 % de la tarifa en 2026 frente a 25,25 % en 2025 (23,0 % y 22,1 % ponderada), y deja propina el 95 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 27,6 % al 25,3 % de los viajes (936.118 → 921.190 con tarifa > 0) y cuya propina se mantiene en torno al 1,7 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 bajan del 28,6 % al 26,7 % de las filas leídas. La tarjeta gana peso entre las formas de pago: del 62,1 % al 64,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] · [E4.4 Regla R05: viajes sin cantidad de pasajeros][E4.4]

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
| 2026 | 6 | 298.141 | 56,19 | 168.473 | 133.018 |
| 2025 | 6 | 346.603 | 57,75 | 202.051 | 148.720 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 14,0 % (346.603 → 298.141) mientras el total de la ciudad baja un 10,0 %, así que su peso cae del 8,6 % al 8,2 % de los viajes. Por aeropuerto, JFK cae −16,6 % y LaGuardia cae −10,6 %. La tarifa promedio baja de US$ 57,75 a US$ 56,19 (−2,7 %), pero esa baja está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 325.478,05 (de Midtown Center a JFK Airport, 20,6 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 56,78 a US$ 56,15 (−1,1 %), y la mediana baja de US$ 56,90 a US$ 55,50. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]

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
| 3.646.879 | 4.050.910 | -404.031 | -9,97 | 21,39 | 19,70 | 8,57 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Junio 2026 tuvo 3.646.879 viajes válidos contra 4.050.910 en junio 2025: −404.031 viajes (−9,97 %). La recaudación total (total_amount) cae un 3,1 %, de US$ 115,1 M a US$ 111,6 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario casi no influye: junio 2026 tuvo 5 martes (días flojos), y junio 2025, 5 domingos (días flojos). Todos los días de la semana caen (por día), entre −7 % y −14 %, así que la baja es general.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 8,57 % (de US$ 19,70 a US$ 21,39); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 325.478) la suba es del 9,0 % (de US$ 19,62 a US$ 21,38). La mediana pasa de US$ 14,65 a US$ 15,60 (+6,5 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de junio 2026 hay menos viajes Flex Fare, que son más caros (US$ 26,08 contra US$ 19,79 del resto) y pasan del 28 % al 25 % de los viajes, menos viajes a aeropuertos (del 8,6 % al 8,2 %) y menos viajes de más de 10 millas (del 8,1 % al 6,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,04 a US$ 19,79). El viaje promedio es más corto: 3,39 contra 3,61 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 6,29 % al 4,96 % de las filas leídas (190.369 filas en junio 2026 y 272.050 en junio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,34 % contra 3,13 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,30 % contra 1,59 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en junio 2026 (−10,0 % de viajes, −3,1 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−16,6 %), Penn Station/Madison Sq West (−15,1 %) y Times Sq/Theatre District (−12,7 %).
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 74,2 % de los viajes de junio 2026, contra 73,7 % en junio 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más corto (3,39 contra 3,61 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,65 → US$ 15,60). La propina con tarjeta sube (25,3 % → 26,4 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Los promedios son frágiles: 68 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 325.478,05, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (junio 2026: columna nueva ignorada: request_source). La cuarentena es del 4,96 % y del 6,29 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-06 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-06`](http://localhost:8090/superset/dashboard/respaldo-local-2026-06/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 334 números en este reporte, 334 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:24 UTC, corrida `20261124T022142Z-3c2cd6`).

- Tablero `respaldo-local-2026-06`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.668 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 334 de 334 se ven en los charts que cita su bloque.
<!-- VERIFICACION:END -->

| chart | qué sustenta | tabla | dónde se cita |
|---|---|---|---|
| [E0.1 Viajes válidos del mes][E0.1] | viajes válidos del mes | `marts.ev_indicadores` | Resumen |
| [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] | viajes válidos del mes de comparación | `marts.ev_indicadores` | Resumen |
| [E0.3 Variación de viajes (%)][E0.3] | variación interanual de los viajes | `marts.ev_indicadores` | Resumen |
| [E0.4 Recaudación del mes (USD)][E0.4] | recaudación total del mes | `marts.ev_indicadores` | Resumen |
| [E0.6 Variación de la recaudación (%)][E0.6] | variación interanual de la recaudación | `marts.ev_indicadores` | Resumen |
| [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] | filas leídas, aceptadas, en cuarentena y con advertencias de cada archivo | `marts.ev_calidad` | Calidad, Pregunta 6 |
| [EC.2 Filas que violan cada regla de calidad][EC.2] | filas y porcentaje por regla en los dos meses | `marts.ev_reglas` | Calidad, Pregunta 6 |
| [EC.4 Contrato de esquema: novedades de cada archivo][EC.4] | qué trajo cada parquet respecto del contrato y qué se hizo | `marts.ev_esquema` | Calidad |
| [E1.1 Top 10 de zonas de pickup del mes][E1.1] | respuesta de la pregunta 1 | `marts.ev_zonas` | Pregunta 1 |
| [E1.3 Top 10 del mismo mes del año anterior][E1.3] | quién encabezaba, quién entra y quién sale | `marts.ev_zonas` | Pregunta 1 |
| [E1.4 Concentración y composición del top 10][E1.4] | peso del top 10, zonas en Manhattan, zonas que crecen o caen y total de la ciudad | `marts.ev_indicadores` | Pregunta 1 |
| [E1.5 Pickups en JFK y LaGuardia][E1.5] | puesto y variación de los dos aeropuertos | `marts.ev_zonas` | Pregunta 1 |
| [E1.6 Pickups por borough][E1.6] | peso y variación de cada borough | `marts.ev_boroughs` | Pregunta 1 |
| [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1] | respuesta de la pregunta 2 y sus causas, hora por hora | `marts.ev_horas` | Pregunta 2, Conclusiones |
| [E2.5 Hora de mayor ingreso, hora pico y referencias del mes][E2.5] | resumen de la pregunta 2 | `marts.ev_indicadores` | Pregunta 2 |
| [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] | respuesta de la pregunta 3 (total del mes) y el efecto de la fecha de inicio | `marts.ev_indicadores` | Pregunta 3 |
| [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3] | respuesta de la pregunta 3 (zonas con 1.000 viajes o más) | `marts.ev_cbd_zonas` | Pregunta 3 |
| [E3.2 Proporción diaria de viajes con peaje (%)][E3.2] | cuándo empieza el cobro | `marts.ev_dias` | Pregunta 3 |
| [E3.5 Regla R10: cobros anómalos del peaje][E3.5] | filas marcadas por la regla R10 | `marts.ev_reglas` | Pregunta 3 |
| [E4.1 Propina como % de la tarifa, por forma de pago][E4.1] | respuesta de la pregunta 4 y peso de cada forma de pago | `marts.ev_pagos` | Pregunta 4 |
| [E4.4 Regla R05: viajes sin cantidad de pasajeros][E4.4] | advertencias por passenger_count | `marts.ev_reglas` | Pregunta 4 |
| [E5.1 Viajes y tarifas de los aeropuertos][E5.1] | respuesta de la pregunta 5 | `marts.ev_indicadores` | Pregunta 5 |
| [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4] | los viajes atípicos, con su recorrido y forma de pago | `marts.ev_tarifas_altas` | Pregunta 5, Pregunta 6 |
| [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] | respuesta de la pregunta 6 | `marts.ev_indicadores` | Pregunta 6 |
| [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] | cuántas veces aparece cada día y sus viajes por día | `marts.ev_dias_semana` | Pregunta 6 |
| [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5] | qué cambió en la composición de los viajes | `marts.ev_indicadores` | Pregunta 6 |
| [C1.1 Demanda: viajes y recaudación][C1.1] | conclusión 1, crecimiento o caída | `marts.ev_indicadores` | Conclusiones |
| [C1.2 Las 10 zonas que más mueven el total][C1.2] | conclusión 1, zonas que más suman o pierden viajes | `marts.ev_zonas` | Conclusiones |
| [C1.3 Aeropuertos contra el total de la ciudad][C1.3] | conclusión 1, aeropuertos | `marts.ev_zonas` | Conclusiones |
| [C2.1 Alcance del peaje CBD en los dos meses][C2.1] | conclusión 2, alcance del peaje | `marts.ev_indicadores` | Conclusiones |
| [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2] | conclusión 2, demanda donde se cobra el peaje | `marts.ev_cbd_zonas` | Conclusiones |
| [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1] | conclusión 3, viaje promedio | `marts.ev_indicadores` | Conclusiones |
| [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] | conclusión 4, promedios con y sin atípicas | `marts.ev_indicadores` | Conclusiones |
| [C4.2 Los viajes con las tarifas más altas][C4.2] | conclusión 4, cuáles son | `marts.ev_tarifas_altas` | Conclusiones |
| [C5.1 Cuarentena y reconciliación][C5.1] | conclusión 5, calidad | `marts.ev_calidad` | Conclusiones |
| [C5.2 Cambios de formato de los archivos][C5.2] | conclusión 5, esquema | `marts.ev_esquema` | Conclusiones |

Charts de apoyo visual del mismo tablero (mismas tablas): [E0.5 Recaudación, mismo mes del año anterior (USD)][E0.5], [E0.7 Viajes por día del mes][E0.7], [E0.8 Recaudación por día del mes (USD)][E0.8], [EC.3 Porcentaje de las filas leídas que viola cada regla][EC.3], [E1.2 Viajes del top 10, los dos meses][E1.2], [E1.7 Variación de pickups por borough (%)][E1.7], [E1.8 Todas las zonas y su variación][E1.8], [E2.2 Ingreso promedio por viaje según la hora (USD)][E2.2], [E2.3 Viajes según la hora][E2.3], [E2.4 Viajes de aeropuerto según la hora (%)][E2.4], [E3.4 Las 15 zonas con mayor proporción de viajes con peaje (%)][E3.4], [E4.2 Participación de cada forma de pago (%)][E4.2], [E4.3 Propina media por forma de pago (% de la tarifa)][E4.3], [E5.2 Viajes que tocan cada aeropuerto][E5.2], [E5.3 Tarifa de los viajes de aeropuerto (USD)][E5.3], [E6.3 Viajes por día, según el día de la semana][E6.3], [E6.4 Variación de los viajes por día (%)][E6.4], [E6.6 Tarifa media, media sin atípicas y mediana (USD)][E6.6].

<details><summary>Cada cifra y el chart donde se ve</summary>

Cuando un número redondeado aparece en más de una celda se indica cuántas.

| sección | cifra | chart | columna y fila |
|---|---:|---|---|
| Resumen | 3.646.879 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −10,0 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 4.050.910 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 111,6 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | −3,1 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.837.248 | EC.1 | `filas_archivo` · 2026-06 (y 1 más) |
| Calidad | 3.837.248 | EC.1 | `filas_archivo` · 2026-06 (y 1 más) |
| Calidad | 3.646.879 | EC.1 | `aceptadas` · 2026-06 |
| Calidad | 190.369 | EC.1 | `cuarentena` · 2026-06 |
| Calidad | 4,96 | EC.1 | `pct_cuarentena` · 2026-06 |
| Calidad | 936.142 | EC.1 | `con_advertencias` · 2026-06 |
| Calidad | 24,40 | EC.1 | `pct_advertencias` · 2026-06 |
| Calidad | 4.322.960 | EC.1 | `filas_archivo` · 2025-06 (y 1 más) |
| Calidad | 4.322.960 | EC.1 | `filas_archivo` · 2025-06 (y 1 más) |
| Calidad | 4.050.910 | EC.1 | `aceptadas` · 2025-06 |
| Calidad | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Calidad | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Calidad | 1.143.555 | EC.1 | `con_advertencias` · 2025-06 |
| Calidad | 26,45 | EC.1 | `pct_advertencias` · 2025-06 |
| Calidad | 17 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 20 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 49.807 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,30 | EC.2 | `pct_mes` · R02 |
| Calidad | 68.583 | EC.2 | `filas_anterior` · R02 |
| Calidad | 1,59 | EC.2 | `pct_anterior` · R02 |
| Calidad | −0,29 | EC.2 | `cambio_pp` · R02 |
| Calidad | 128.255 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,34 | EC.2 | `pct_mes` · R03 |
| Calidad | 135.160 | EC.2 | `filas_anterior` · R03 |
| Calidad | 3,13 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,22 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.312 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,37 | EC.2 | `pct_mes` · R04 |
| Calidad | 74.257 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,72 | EC.2 | `pct_anterior` · R04 |
| Calidad | −1,34 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.023.916 | EC.2 | `filas_mes` · R05 |
| Calidad | 26,68 | EC.2 | `pct_mes` · R05 |
| Calidad | 1.235.737 | EC.2 | `filas_anterior` · R05 |
| Calidad | 28,59 | EC.2 | `pct_anterior` · R05 |
| Calidad | −1,90 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 12 más) |
| Calidad | 18.385 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,48 | EC.2 | `pct_mes` · R08 |
| Calidad | 280.005 | EC.2 | `filas_anterior` · R08 |
| Calidad | 6,48 | EC.2 | `pct_anterior` · R08 |
| Calidad | −6,00 | EC.2 | `cambio_pp` · R08 |
| Calidad | 992 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 |
| Calidad | 1.522 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,04 | EC.2 | `pct_anterior` · R09 |
| Calidad | −0,01 | EC.2 | `cambio_pp` · R09 |
| Calidad | 9.424 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,25 | EC.2 | `pct_mes` · R10 |
| Calidad | 49.930 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,15 | EC.2 | `pct_anterior` · R10 |
| Calidad | −0,91 | EC.2 | `cambio_pp` · R10 |
| Calidad | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Calidad | 4,96 | EC.1 | `pct_cuarentena` · 2026-06 |
| Calidad | 190.369 | EC.1 | `cuarentena` · 2026-06 |
| Calidad | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Calidad | 3,34 | EC.2 | `pct_mes` · R03 |
| Calidad | 3,13 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,30 | EC.2 | `pct_mes` · R02 |
| Calidad | 1,59 | EC.2 | `pct_anterior` · R02 |
| Calidad | −1,34 | EC.2 | `cambio_pp` · R04 |
| Calidad | 936.142 | EC.1 | `con_advertencias` · 2026-06 |
| Calidad | 24,4 | EC.1 | `pct_advertencias` · 2026-06 |
| Calidad | 26,7 | EC.2 | `pct_mes` · R05 |
| Calidad | 28,6 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 170.750 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 169.806 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 944 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 0,56 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 154.901 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 168.094 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -13.193 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -7,85 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 149.903 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 147.490 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 2.413 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 1,64 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 142.206 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 170.532 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -28.326 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -16,61 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 114.952 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 122.379 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -7.427 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -6,07 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 107.116 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 108.997 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -1.881 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -1,73 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 105.994 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 121.466 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -15.472 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -12,74 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 103.514 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 121.977 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -18.463 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -15,14 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 98.996 | E1.1 | `viajes_mes` · Murray Hill Manhattan |
| Pregunta 1 | 108.371 | E1.1 | `viajes_anterior` · Murray Hill Manhattan |
| Pregunta 1 | -9.375 | E1.1 | `variacion` · Murray Hill Manhattan |
| Pregunta 1 | -8,65 | E1.1 | `variacion_pct` · Murray Hill Manhattan |
| Pregunta 1 | 97.889 | E1.1 | `viajes_mes` · LaGuardia Airport Queens |
| Pregunta 1 | 108.948 | E1.1 | `viajes_anterior` · LaGuardia Airport Queens |
| Pregunta 1 | -11.059 | E1.1 | `variacion` · LaGuardia Airport Queens |
| Pregunta 1 | -10,15 | E1.1 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | +0,6 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 2 más) |
| Pregunta 1 | +1,6 | E1.1 | `variacion_pct` · Upper East Side North Manhattan (y 1 más) |
| Pregunta 1 | −1,7 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan (y 1 más) |
| Pregunta 1 | −16,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 170.750 | E1.1 | `viajes_mes` · Upper East Side South Manhattan (y 1 más) |
| Pregunta 1 | +0,6 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 2 más) |
| Pregunta 1 | 4 | E1.1 | `puesto_anterior` · Upper East Side North Manhattan (y 5 más) |
| Pregunta 1 | −16,6 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 10 | E1.1 | `puesto_anterior` · Murray Hill Manhattan (y 11 más) |
| Pregunta 1 | −10,2 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | −10,0 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 34,2 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 33,3 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 33.860 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 13.865 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −10,0 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `distancia_media_mes` · 4:00 (y 10 más) |
| Pregunta 2 | 33.068 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 35,27 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 5 | E2.1 | `distancia_media_mes` · 4:00 (y 10 más) |
| Pregunta 2 | 33.295 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 32,56 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `distancia_media_mes` · 4:00 (y 12 más) |
| Pregunta 2 | 18:00 | E2.1 | `pct_aeropuerto_mes` · 5:00 (y 5 más) |
| Pregunta 2 | 5:00 | E2.1 | `distancia_media_mes` · 4:00 (y 12 más) |
| Pregunta 2 | 14:00 | E2.1 | `puesto_anterior` · 12:00 (y 2 más) |
| Pregunta 2 | 35,27 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 2 más) |
| Pregunta 2 | 32,56 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 33.068 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 231.475 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 17,9 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,2 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 4 más) |
| Pregunta 2 | 5,43 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,39 | E2.1 | `distancia_media_mes` · 14:00 (y 1 más) |
| Pregunta 2 | 16,1 | E2.1 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 17,9 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,3 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 4 más) |
| Pregunta 2 | 5,78 | E2.1 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 5,43 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 30,80 | E2.1 | `ingreso_viaje_anterior` · 14:00 |
| Pregunta 2 | 325.478,05 | E2.1 | `tarifa_maxima_anterior` · 14:00 |
| Pregunta 2 | 29,40 | E2.1 | `ingreso_sin_atipicas_anterior` · 14:00 |
| Pregunta 3 | 3.646.879 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.707.309 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 74,24 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 103.514 | E3.3 | `viajes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 102.830 | E3.3 | `viajes_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 99,34 | E3.3 | `pct_con_peaje` · Penn Station/Madison Sq West Manhattan |
| Pregunta 3 | 114.952 | E3.3 | `viajes` · Midtown East Manhattan |
| Pregunta 3 | 113.973 | E3.3 | `viajes_con_peaje` · Midtown East Manhattan |
| Pregunta 3 | 99,15 | E3.3 | `pct_con_peaje` · Midtown East Manhattan (y 1 más) |
| Pregunta 3 | 60.696 | E3.3 | `viajes` · Sutton Place/Turtle Bay North Manhattan |
| Pregunta 3 | 60.179 | E3.3 | `viajes_con_peaje` · Sutton Place/Turtle Bay North Manhattan |
| Pregunta 3 | 99,15 | E3.3 | `pct_con_peaje` · Midtown East Manhattan (y 1 más) |
| Pregunta 3 | 1.093 | E3.3 | `viajes` · Battery Park Manhattan |
| Pregunta 3 | 1.083 | E3.3 | `viajes_con_peaje` · Battery Park Manhattan |
| Pregunta 3 | 99,09 | E3.3 | `pct_con_peaje` · Battery Park Manhattan |
| Pregunta 3 | 93.796 | E3.3 | `viajes` · Midtown North Manhattan |
| Pregunta 3 | 92.881 | E3.3 | `viajes_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 99,02 | E3.3 | `pct_con_peaje` · Midtown North Manhattan |
| Pregunta 3 | 74,24 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.707.309 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.646.879 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 99 | E3.3 | `pct_con_peaje` · Penn Station/Madison Sq West Manhattan (y 4 más) |
| Pregunta 3 | 73,75 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 (y 1 más) |
| Pregunta 3 | +0,5 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.424 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 921.190 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,71 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,53 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 6 más) |
| Pregunta 4 | 2.367.555 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 26,36 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 23,05 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 338.611 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge |
| Pregunta 4 | 6.419 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 11.058 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 3 más) |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 3 más) |
| Pregunta 4 | 936.118 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,49 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 1,49 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 6 más) |
| Pregunta 4 | 2.517.597 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,13 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 4 | 351.739 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge |
| Pregunta 4 | 14.062 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,07 | E4.1 | `propina_media_pct_anterior` · No charge |
| Pregunta 4 | 0,11 | E4.1 | `propina_ponderada_pct_anterior` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 48.613 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_media_pct_anterior` · Dispute |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 5 | E4.1 | `payment_type` · Unknown |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 6 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 13 más) |
| Pregunta 4 | 26,36 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 23,0 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,1 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 95 | E4.1 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 27,6 | E4.1 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 25,3 | E4.1 | `participacion_mes_pct` · Flex Fare (y 1 más) |
| Pregunta 4 | 936.118 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 921.190 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,7 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 28,6 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 26,7 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 62,1 | E4.1 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 64,9 | E4.1 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 298.141 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,19 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 168.473 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 133.018 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 346.603 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,75 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 202.051 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 148.720 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 14,0 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia (y 2 más) |
| Pregunta 5 | 346.603 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 298.141 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 10,0 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 8,6 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,2 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −16,6 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −10,6 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 57,75 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 56,19 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −2,7 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 325.478,05 | E5.1 | `valor_anterior` · Tarifa máxima de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 20,6 | E5.4 | `distancia_millas` · 2025-06 Cash puesto 1 |
| Pregunta 5 | 56,78 | E5.1 | `valor_anterior` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 56,15 | E5.1 | `valor_mes` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | −1,1 | E5.1 | `variacion_pct` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 56,90 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 55,50 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.646.879 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 4.050.910 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -404.031 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -9,97 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 21,39 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 19,70 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 8,57 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.646.879 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 4.050.910 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −404.031 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −9,97 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 3,1 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 115,1 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 111,6 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | −7 | E6.2 | `variacion_por_dia_pct` · viernes |
| Pregunta 6 | −14 | E6.2 | `variacion_por_dia_pct` · martes |
| Pregunta 6 | 8,57 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 19,70 | E6.1 | `valor_anterior` · Tarifa media |
| Pregunta 6 | 21,39 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 325.478 | E6.1 | `valor_anterior` · Tarifa máxima (y 1 más) |
| Pregunta 6 | 9,0 | E6.1 | `variacion_pct` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 19,62 | E6.1 | `valor_anterior` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 21,38 | E6.1 | `valor_mes` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 14,65 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 15,60 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +6,5 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 26,08 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 19,79 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 28 | E6.5 | `valor_anterior` · Participación de Flex Fare |
| Pregunta 6 | 25 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 8,6 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,2 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,1 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 6,9 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 20,04 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 19,79 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,39 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,61 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Pregunta 6 | 4,96 | EC.1 | `pct_cuarentena` · 2026-06 |
| Pregunta 6 | 190.369 | EC.1 | `cuarentena` · 2026-06 |
| Pregunta 6 | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Pregunta 6 | 3,34 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 3,13 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,30 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 1,59 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −10,0 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | −3,1 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −16,6 | C1.2 | `variacion_pct` · JFK Airport Queens (y 1 más) |
| Conclusiones | −15,1 | C1.2 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Conclusiones | −12,7 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | 74,2 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 73,7 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,39 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,61 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,65 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 15,60 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,3 | C3.1 | `valor_mes` · Participación de Flex Fare (y 1 más) |
| Conclusiones | 26,4 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 68 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 325.478,05 | C4.1 | `valor_anterior` · Tarifa máxima (y 2 más) |
| Conclusiones | 4,96 | C5.1 | `pct_cuarentena` · 2026-06 |
| Conclusiones | 6,29 | C5.1 | `pct_cuarentena` · 2025-06 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-06/#CHART-C5-2
