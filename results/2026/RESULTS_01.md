# Resultados: enero 2026 vs enero 2025

> En enero 2026 los taxis amarillos hicieron 3.517.270 viajes válidos, +5,8 % que en enero 2025 (3.323.437), con una recaudación de US$ 104,3 M (+18,1 %).

| | |
|---|---|
| Comando | `make all MES=2026-01 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-01.parquet` y `yellow_tripdata_2025-01.parquet` |
| Corrida | `20261118T045126Z-bd0e50`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=01/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-01 | `yellow_tripdata_2026-01.parquet` | 3.724.889 | 3.724.889 | 3.517.270 | 207.619 | 5,57 % | 1.012.510 (27,18 %) | sí |
| 2025-01 | `yellow_tripdata_2025-01.parquet` | 3.475.226 | 3.475.226 | 3.323.437 | 151.789 | 4,37 % | 511.679 (14,72 %) | sí |

| regla | severidad | qué controla | 2026-01 | 2025-01 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 22 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 45.070 (1,21 %) | 2.051 (0,06 %) | +1,15 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 125.900 (3,38 %) | 91.055 (2,62 %) | +0,76 pp |
| R04 | reject | Total cobrado faltante o negativo. | 39.984 (1,07 %) | 63.037 (1,81 %) | −0,74 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.102.845 (29,61 %) | 564.805 (16,25 %) | +13,36 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 43.829 (1,18 %) | 148.413 (4,27 %) | −3,09 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 874 (0,02 %) | 982 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 25.197 (0,68 %) | 6.954 (0,20 %) | +0,48 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 4,37 % al 5,57 % de las filas leídas (207.619 filas en enero 2026 y 151.789 en enero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,38 % contra 2,62 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,21 % contra 0,06 %).
- Las reglas de advertencia no sacan filas: 1.012.510 filas aceptadas de enero 2026 (27,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 29,6 %, contra 16,3 % en enero 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de enero 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de enero 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 152.527 | 159.330 | -6.803 | -4,27 |
| Manhattan | Upper East Side North | 145.704 | 151.616 | -5.912 | -3,90 |
| Queens | JFK Airport | 141.563 | 134.804 | 6.759 | 5,01 |
| Manhattan | Midtown Center | 139.233 | 163.866 | -24.633 | -15,03 |
| Manhattan | Penn Station/Madison Sq West | 105.640 | 115.021 | -9.381 | -8,16 |
| Manhattan | Lincoln Square East | 104.679 | 107.540 | -2.861 | -2,66 |
| Manhattan | Midtown East | 103.675 | 113.840 | -10.165 | -8,93 |
| Manhattan | Times Sq/Theatre District | 100.860 | 120.657 | -19.797 | -16,41 |
| Manhattan | East Village | 96.387 | 78.843 | 17.544 | 22,25 |
| Manhattan | Upper West Side South | 92.423 | 93.831 | -1.408 | -1,50 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, dos crecen (entre +5,0 % en JFK Airport y +22,3 % en East Village) y ocho caen (entre −1,5 % en Upper West Side South y −16,4 % en Times Sq/Theatre District). Upper East Side South lidera con 152.527 viajes (−4,3 %) y desplaza a Midtown Center, que encabezaba enero 2025. Respecto de enero 2025 entra al top 10 East Village y sale Midtown North. En los aeropuertos, JFK (puesto 3 del top) crece +5,0 % y LaGuardia (fuera del top) cae −5,9 %: LaGuardia va peor que el total de la ciudad y JFK queda en línea con él (+5,8 %). La demanda además se reparte más: el top 10 concentra el 33,6 % de los pickups, frente al 37,7 % de 2025. Fuera de Manhattan, el Bronx casi triplica sus pickups (13.237 → 35.257), aunque sobre una base chica, contra +5,8 % del total.

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
| 2026 | 1 | 5 | 31.751 | 34,74 |
| 2025 | 1 | 5 | 21.233 | 33,64 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 34,74 en 2026 y US$ 33,64 en 2025. Es una hora de poco volumen (31.751 viajes, contra 229.629 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 14,7 % de sus viajes toca JFK o LaGuardia (contra 7,5 % en todo el mes) y la distancia media es de 5,88 millas (contra 3,49). En 2026 la distancia media sube (de 5,71 a 5,88 millas), por eso el ingreso por viaje sube un 3,3 %, aunque los viajes de aeropuerto son menos (del 20,8 % al 14,7 % de los viajes de las 5:00). Ojo con el segundo puesto de 2025 (las 12:00, US$ 30,68): es artificial, porque lo infla un viaje con una tarifa de US$ 863.372,12. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 25,59.

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
| ALL ZONES |  | 3.517.270 | 2.493.412 | 70,89 |
| Greenwich Village South | Manhattan | 50.464 | 50.334 | 99,74 |
| SoHo | Manhattan | 26.507 | 26.433 | 99,72 |
| West Village | Manhattan | 76.135 | 75.831 | 99,60 |
| East Village | Manhattan | 96.387 | 95.951 | 99,55 |
| Little Italy/NoLiTa | Manhattan | 37.370 | 37.190 | 99,52 |

**Interpretación:** El 70,89 % de los viajes de enero 2026 pagó cbd_congestion_fee (2.493.412 de 3.517.270, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, SoHo, West Village, East Village y Little Italy/NoLiTa, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En enero 2025 lo pagaba el 65,98 % de los viajes (un mes diluido: el peaje empezó el 5 de enero): la proporción sube +4,9 pp. La regla R10 marcó 25.197 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 1 | 0 | Flex Fare | 994.414 | 1,79 | 1,50 |
| 2026 | 1 | 1 | Credit card | 2.192.696 | 25,03 | 21,18 |
| 2026 | 1 | 2 | Cash | 292.394 | 0,00 | 0,00 |
| 2026 | 1 | 3 | No charge | 8.986 | 0,01 | 0,00 |
| 2026 | 1 | 4 | Dispute | 27.581 | 0,00 | 0,01 |
| 2025 | 1 | 0 | Flex Fare | 412.946 | 2,74 | 3,02 |
| 2025 | 1 | 1 | Credit card | 2.423.279 | 26,29 | 22,94 |
| 2025 | 1 | 2 | Cash | 367.786 | 0,00 | 0,00 |
| 2025 | 1 | 3 | No charge | 12.025 | 0,01 | 0,02 |
| 2025 | 1 | 4 | Dispute | 35.497 | 0,03 | 0,02 |

**Interpretación:** Con tarjeta de crédito la propina baja: 25,03 % de la tarifa en 2026 frente a 26,29 % en 2025 (21,2 % y 22,9 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 14,6 % al 28,3 % de los viajes (412.946 → 994.414 con tarifa > 0) y cuya propina cae del 2,74 % al 1,79 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 16,3 % al 29,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 72,9 % al 62,3 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 1 | 264.121 | 55,51 | 160.729 | 106.055 |
| 2025 | 1 | 270.966 | 58,03 | 157.420 | 116.346 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 2,5 % (270.966 → 264.121) mientras el total de la ciudad sube un 5,8 %, así que su peso cae del 8,2 % al 7,5 % de los viajes. Por aeropuerto, JFK crece +2,1 % y LaGuardia cae −8,8 %. La tarifa promedio baja de US$ 58,03 a US$ 55,51 (−4,4 %), pero esa baja no es real: la produce un solo viaje de 2025 con fare_amount = US$ 863.372,12 (de LaGuardia Airport a Astoria Park, 1,6 millas, pago Dispute). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 54,82 a US$ 55,49 (+1,2 %), y la mediana sube de US$ 52,70 a US$ 54,10. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.517.270 | 3.323.437 | 193.833 | 5,83 | 21,08 | 17,73 | 18,88 |

**Interpretación:**

- Enero 2026 tuvo 3.517.270 viajes válidos contra 3.323.437 en enero 2025: +193.833 viajes (+5,83 %). La recaudación total (total_amount) crece un 18,1 %, de US$ 88,3 M a US$ 104,3 M.
- Parte del salto es de calendario: enero 2026 tuvo 5 sábados (días fuertes), y enero 2025, 5 miércoles. Con el calendario de 2025 la variación sería +5,5 %. Por día de la semana la variación va de −8 % a +13 %: el cambio no es parejo.
- La tarifa promedio sube un 18,88 % (de US$ 17,73 a US$ 21,08); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 863.372) la suba es del 20,6 % (de US$ 17,47 a US$ 21,07). La mediana pasa de US$ 12,80 a US$ 15,60 (+21,9 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de enero 2026 hay más viajes Flex Fare, que son más caros (US$ 25,16 contra US$ 19,46 del resto) y pasan del 15 % al 28 % de los viajes, menos viajes a aeropuertos (del 8,2 % al 7,5 %) y más viajes de más de 10 millas (del 6,8 % al 7,7 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 8,6 % (de US$ 17,91 a US$ 19,46). El viaje promedio es más largo: 3,49 contra 3,16 millas.
- Calidad: la cuarentena sube del 4,37 % al 5,57 % de las filas leídas (207.619 filas en enero 2026 y 151.789 en enero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,38 % contra 2,62 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,21 % contra 0,06 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece en forma moderada en enero 2026 (+5,8 % de viajes, +18,1 % de recaudación). Las zonas que más suman viajes son East Village (+22,3 %), Lower East Side (+27,0 %) y Kips Bay (+22,9 %).
- El peaje de congestión (CBD) alcanza al 70,9 % de los viajes de enero 2026, contra 66,0 % en enero 2025.
- El viaje promedio es más largo (3,49 contra 3,16 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 12,80 → US$ 15,60). La propina con tarjeta baja (26,3 % → 25,0 %).
- Los promedios son frágiles: 43 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 863.372,12, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 5,57 % y del 4,37 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-01 INGEST_MODE=direct WAREHOUSE=duckdb`.
