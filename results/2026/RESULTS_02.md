# Resultados: febrero 2026 vs febrero 2025

> En febrero 2026 los taxis amarillos hicieron 3.210.995 viajes válidos, −6,1 % que en febrero 2025 (3.421.132), con una recaudación de US$ 97,8 M (+10,4 %).

| | |
|---|---|
| Comando | `make all MES=2026-02 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-02.parquet` y `yellow_tripdata_2025-02.parquet` |
| Corrida | `20261118T045128Z-97cfbe`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=02/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-02 | `yellow_tripdata_2026-02.parquet` | 3.399.866 | 3.399.866 | 3.210.995 | 188.871 | 5,56 % | 943.856 (27,76 %) | sí |
| 2025-02 | `yellow_tripdata_2025-02.parquet` | 3.577.543 | 3.577.543 | 3.421.132 | 156.411 | 4,37 % | 767.302 (21,45 %) | sí |

| regla | severidad | qué controla | 2026-02 | 2025-02 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 16 (0,00 %) | 31 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 40.598 (1,19 %) | 5.164 (0,14 %) | +1,05 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 123.422 (3,63 %) | 99.943 (2,79 %) | +0,84 pp |
| R04 | reject | Total cobrado faltante o negativo. | 27.291 (0,80 %) | 55.179 (1,54 %) | −0,74 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.036.201 (30,48 %) | 828.688 (23,16 %) | +7,31 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 30.449 (0,90 %) | 186.623 (5,22 %) | −4,32 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 762 (0,02 %) | 841 (0,02 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 17.479 (0,51 %) | 37.238 (1,04 %) | −0,53 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 4,37 % al 5,56 % de las filas leídas (188.871 filas en febrero 2026 y 156.411 en febrero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,63 % contra 2,79 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,19 % contra 0,14 %).
- Las reglas de advertencia no sacan filas: 943.856 filas aceptadas de febrero 2026 (27,8 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 30,5 %, contra 23,2 % en febrero 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de febrero 2026: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de febrero 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Upper East Side South | 138.289 | 152.770 | -14.481 | -9,48 |
| Manhattan | Upper East Side North | 131.418 | 143.712 | -12.294 | -8,55 |
| Manhattan | Midtown Center | 128.649 | 155.533 | -26.884 | -17,29 |
| Queens | JFK Airport | 116.974 | 115.233 | 1.741 | 1,51 |
| Manhattan | Midtown East | 94.729 | 109.808 | -15.079 | -13,73 |
| Manhattan | Penn Station/Madison Sq West | 94.276 | 109.148 | -14.872 | -13,63 |
| Manhattan | East Village | 90.240 | 93.197 | -2.957 | -3,17 |
| Manhattan | Lincoln Square East | 89.942 | 101.271 | -11.329 | -11,19 |
| Manhattan | Times Sq/Theatre District | 86.595 | 109.839 | -23.244 | -21,16 |
| Manhattan | Union Sq | 84.896 | 98.966 | -14.070 | -14,22 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, una crece (+1,5 % en JFK Airport) y nueve caen (entre −3,2 % en East Village y −21,2 % en Times Sq/Theatre District). Upper East Side South lidera con 138.289 viajes (−9,5 %) y desplaza a Midtown Center, que encabezaba febrero 2025. En los aeropuertos, JFK (puesto 4 del top) crece +1,5 % y LaGuardia (fuera del top) cae −10,3 %: LaGuardia va peor que el total de la ciudad y JFK va mejor (−6,1 %). La demanda además se reparte más: el top 10 concentra el 32,9 % de los pickups, frente al 34,8 % de 2025. Fuera de Manhattan, el Bronx crece +65,3 % en sus pickups (20.022 → 33.089), aunque sobre una base chica, contra −6,1 % del total.

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
| 2026 | 2 | 5 | 30.568 | 36,52 |
| 2025 | 2 | 5 | 23.365 | 32,29 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 36,52 en 2026 y US$ 32,29 en 2025. Es una hora de poco volumen (30.568 viajes, contra 220.354 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 13,8 % de sus viajes toca JFK o LaGuardia (contra 7,1 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,43). El ingreso por viaje de esa hora sube un 13,1 % aunque los viajes de aeropuerto son menos (del 18,2 % al 13,8 % de los viajes de las 5:00): lo explican las tarifas y recargos de 2026.

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
| ALL ZONES |  | 3.210.995 | 2.277.558 | 70,93 |
| SoHo | Manhattan | 24.968 | 24.903 | 99,74 |
| Greenwich Village South | Manhattan | 47.321 | 47.171 | 99,68 |
| West Village | Manhattan | 71.603 | 71.371 | 99,68 |
| East Village | Manhattan | 90.240 | 89.845 | 99,56 |
| Midtown North | Manhattan | 75.634 | 75.287 | 99,54 |

**Interpretación:** El 70,93 % de los viajes de febrero 2026 pagó cbd_congestion_fee (2.277.558 de 3.210.995, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, East Village y Midtown North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En febrero 2025 lo pagaba el 74,09 % de los viajes: la proporción baja −3,2 pp. La regla R10 marcó 17.479 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 2 | 0 | Flex Fare | 928.164 | 1,88 | 1,55 |
| 2026 | 2 | 1 | Credit card | 2.000.161 | 24,80 | 21,15 |
| 2026 | 2 | 2 | Cash | 255.450 | 0,00 | 0,00 |
| 2026 | 2 | 3 | No charge | 6.704 | 0,01 | 0,01 |
| 2026 | 2 | 4 | Dispute | 19.061 | 0,01 | 0,03 |
| 2025 | 2 | 0 | Flex Fare | 628.164 | 1,90 | 2,00 |
| 2025 | 2 | 1 | Credit card | 2.312.981 | 26,35 | 22,87 |
| 2025 | 2 | 2 | Cash | 317.947 | 0,00 | 0,00 |
| 2025 | 2 | 3 | No charge | 11.348 | 0,43 | 0,12 |
| 2025 | 2 | 4 | Dispute | 35.028 | 0,08 | 0,09 |

**Interpretación:** Con tarjeta de crédito la propina baja: 24,80 % de la tarifa en 2026 frente a 26,35 % en 2025 (21,2 % y 22,9 % ponderada), y deja propina el 91 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 21,7 % al 28,9 % de los viajes (628.164 → 928.164 con tarifa > 0) y cuya propina se mantiene en torno al 1,9 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 23,2 % al 30,5 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 67,6 % al 62,3 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 2 | 229.500 | 55,58 | 134.384 | 96.976 |
| 2025 | 2 | 242.974 | 54,31 | 135.405 | 109.694 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 5,5 % (242.974 → 229.500) mientras el total de la ciudad baja un 6,1 %, así que su peso se mantiene en el 7,1 % de los viajes. Por aeropuerto, JFK cae −0,8 % y LaGuardia cae −11,6 %. La tarifa promedio sube de US$ 54,31 a US$ 55,58 (+2,3 %), y la mediana sube de US$ 51,30 a US$ 54,10. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.210.995 | 3.421.132 | -210.137 | -6,14 | 21,79 | 17,31 | 25,91 |

**Interpretación:**

- Febrero 2026 tuvo 3.210.995 viajes válidos contra 3.421.132 en febrero 2025: −210.137 viajes (−6,14 %). La recaudación total (total_amount) crece un 10,4 %, de US$ 88,5 M a US$ 97,8 M.
- Los dos meses tienen la misma composición de días de la semana, así que no hay efecto calendario. Todos los días de la semana caen (por día), entre −3 % y −18 %, así que la baja es general.
- La tarifa promedio sube un 25,91 % (de US$ 17,31 a US$ 21,79). La mediana pasa de US$ 12,80 a US$ 16,30 (+27,3 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de febrero 2026 hay más viajes Flex Fare, que son más caros (US$ 27,09 contra US$ 19,63 del resto) y pasan del 22 % al 29 % de los viajes y más viajes de más de 10 millas (del 6,1 % al 7,4 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media sube un 10,4 % (de US$ 17,79 a US$ 19,63). El viaje promedio es más largo: 3,43 contra 3,12 millas.
- Calidad: la cuarentena sube del 4,37 % al 5,56 % de las filas leídas (188.871 filas en febrero 2026 y 156.411 en febrero 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,63 % contra 2,79 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,19 % contra 0,14 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en febrero 2026 (−6,1 % de viajes, +10,4 % de recaudación). Las zonas que más pierden viajes son Midtown Center (−17,3 %), Times Sq/Theatre District (−21,2 %) y Midtown North (−16,8 %).
- El peaje de congestión (CBD) alcanza al 70,9 % de los viajes de febrero 2026, contra 74,1 % en febrero 2025.
- El viaje promedio es más largo (3,43 contra 3,12 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 12,80 → US$ 16,30). La propina con tarjeta baja (26,4 % → 24,8 %).
- Hay 38 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 132.531,36, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los dos archivos respetan el contrato de esquema. La cuarentena es del 5,56 % y del 4,37 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-02 INGEST_MODE=direct WAREHOUSE=duckdb`.
