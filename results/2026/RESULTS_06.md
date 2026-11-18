# Resultados: junio 2026 vs junio 2025

> En junio 2026 los taxis amarillos hicieron 3.646.879 viajes válidos, −10,0 % que en junio 2025 (4.050.910), con una recaudación de US$ 111,6 M (−3,1 %).

| | |
|---|---|
| Comando | `make all MES=2026-06 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-06.parquet` y `yellow_tripdata_2025-06.parquet` |
| Corrida | `20261118T045137Z-1b374d`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=06/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-06 | `yellow_tripdata_2026-06.parquet` | 3.837.248 | 3.837.248 | 3.646.879 | 190.369 | 4,96 % | 936.142 (24,40 %) | sí |
| 2025-06 | `yellow_tripdata_2025-06.parquet` | 4.322.960 | 4.322.960 | 4.050.910 | 272.050 | 6,29 % | 1.143.555 (26,45 %) | sí |

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

- La cuarentena baja del 6,29 % al 4,96 % de las filas leídas (190.369 filas en junio 2026 y 272.050 en junio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,34 % contra 3,13 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,30 % contra 1,59 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,34 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 936.142 filas aceptadas de junio 2026 (24,4 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 26,7 %, contra 28,6 % en junio 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de junio 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de junio 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, dos crecen (entre +0,6 % en Upper East Side South y +1,6 % en Upper East Side North) y ocho caen (entre −1,7 % en Lincoln Square East y −16,6 % en JFK Airport). Upper East Side South lidera con 170.750 viajes (+0,6 %) y desplaza a JFK Airport, que encabezaba junio 2025. En los aeropuertos, JFK (puesto 4 del top) cae −16,6 % y LaGuardia (puesto 10 del top) cae −10,2 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−10,0 %). La demanda se concentra más: el top 10 reúne el 34,2 % de los pickups, frente al 33,3 % de 2025. Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (33.860 → 13.865), aunque sobre una base chica, contra −10,0 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 35,27 en 2026 y US$ 32,56 en 2025. Es una hora de poco volumen (33.068 viajes, contra 231.475 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 17,9 % de sus viajes toca JFK o LaGuardia (contra 8,2 % en todo el mes) y la distancia media es de 5,43 millas (contra 3,39). En 2026 los viajes de aeropuerto son más (del 16,1 % al 17,9 % de los viajes de las 5:00), por eso el ingreso por viaje sube un 8,3 %, aunque la distancia media baja (de 5,78 a 5,43 millas). Ojo con el tercer puesto de 2025 (las 14:00, US$ 30,80): es artificial, porque lo infla un viaje con una tarifa de US$ 325.478,05. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 29,40.

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

**Interpretación:** El 74,24 % de los viajes de junio 2026 pagó cbd_congestion_fee (2.707.309 de 3.646.879, siempre US$ 0,75). Las cinco zonas con mayor proporción (Penn Station/Madison Sq West, Midtown East, Sutton Place/Turtle Bay North, Battery Park y Midtown North, alrededor del 99 %) están todas en Manhattan, dentro de la zona de peaje. En junio 2025 lo pagaba el 73,75 % de los viajes: la proporción sube +0,5 pp. La regla R10 marcó 9.424 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina sube: 26,36 % de la tarifa en 2026 frente a 25,25 % en 2025 (23,0 % y 22,1 % ponderada), y deja propina el 95 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 27,6 % al 25,3 % de los viajes (936.118 → 921.190 con tarifa > 0) y cuya propina se mantiene en torno al 1,7 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 bajan del 28,6 % al 26,7 % de las filas leídas. La tarjeta gana peso entre las formas de pago: del 62,1 % al 64,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 14,0 % (346.603 → 298.141) mientras el total de la ciudad baja un 10,0 %, así que su peso cae del 8,6 % al 8,2 % de los viajes. Por aeropuerto, JFK cae −16,6 % y LaGuardia cae −10,6 %. La tarifa promedio baja de US$ 57,75 a US$ 56,19 (−2,7 %), pero esa baja está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 325.478,05 (de Midtown Center a JFK Airport, 20,6 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 56,78 a US$ 56,15 (−1,1 %), y la mediana baja de US$ 56,90 a US$ 55,50. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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

**Interpretación:**

- Junio 2026 tuvo 3.646.879 viajes válidos contra 4.050.910 en junio 2025: −404.031 viajes (−9,97 %). La recaudación total (total_amount) cae un 3,1 %, de US$ 115,1 M a US$ 111,6 M.
- El calendario casi no influye: junio 2026 tuvo 5 martes (días flojos), y junio 2025, 5 domingos (días flojos). Todos los días de la semana caen (por día), entre −7 % y −14 %, así que la baja es general.
- La tarifa promedio sube un 8,57 % (de US$ 19,70 a US$ 21,39); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 325.478) la suba es del 9,0 % (de US$ 19,62 a US$ 21,38). La mediana pasa de US$ 14,65 a US$ 15,60 (+6,5 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de junio 2026 hay menos viajes Flex Fare, que son más caros (US$ 26,08 contra US$ 19,79 del resto) y pasan del 28 % al 25 % de los viajes, menos viajes a aeropuertos (del 8,6 % al 8,2 %) y menos viajes de más de 10 millas (del 8,1 % al 6,9 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,04 a US$ 19,79). El viaje promedio es más corto: 3,39 contra 3,61 millas.
- Calidad: la cuarentena baja del 6,29 % al 4,96 % de las filas leídas (190.369 filas en junio 2026 y 272.050 en junio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,34 % contra 3,13 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,30 % contra 1,59 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en junio 2026 (−10,0 % de viajes, −3,1 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−16,6 %), Penn Station/Madison Sq West (−15,1 %) y Times Sq/Theatre District (−12,7 %).
- El peaje de congestión (CBD) alcanza al 74,2 % de los viajes de junio 2026, contra 73,7 % en junio 2025.
- El viaje promedio es más corto (3,39 contra 3,61 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,65 → US$ 15,60). La propina con tarjeta sube (25,3 % → 26,4 %).
- Los promedios son frágiles: 68 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 325.478,05, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (junio 2026: columna nueva ignorada: request_source). La cuarentena es del 4,96 % y del 6,29 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-06 INGEST_MODE=direct WAREHOUSE=duckdb`.
