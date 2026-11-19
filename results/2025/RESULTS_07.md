# Resultados: julio 2025 vs julio 2024

> En julio 2025 los taxis amarillos hicieron 3.648.036 viajes válidos, +22,4 % que en julio 2024 (2.981.368), con una recaudación de US$ 102,1 M (+18,5 %).

| | |
|---|---|
| Comando | `make all MES=2025-07 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-07.parquet` y `yellow_tripdata_2024-07.parquet` |
| Corrida | `20261118T045114Z-ea929b`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=07/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-07 | `yellow_tripdata_2025-07.parquet` | 3.898.963 | 3.898.963 | 3.648.036 | 250.927 | 6,44 % | 977.379 (25,07 %) | sí |
| 2024-07 | `yellow_tripdata_2024-07.parquet` | 3.076.903 | 3.076.903 | 2.981.368 | 95.535 | 3,10 % | 301.696 (9,81 %) | sí |

| regla | severidad | qué controla | 2025-07 | 2024-07 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 47 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 56.064 (1,44 %) | 1.068 (0,03 %) | +1,40 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 124.048 (3,18 %) | 48.204 (1,57 %) | +1,61 pp |
| R04 | reject | Total cobrado faltante o negativo. | 76.455 (1,96 %) | 50.379 (1,64 %) | +0,32 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.059.299 (27,17 %) | 308.084 (10,01 %) | +17,16 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 1 (0,00 %) | 1 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 251.281 (6,44 %) | 62.620 (2,04 %) | +4,41 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.043 (0,03 %) | 1.091 (0,04 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 51.044 (1,31 %) | 0 (0,00 %) | +1,31 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,10 % al 6,44 % de las filas leídas (250.927 filas en julio 2025 y 95.535 en julio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,18 % contra 1,57 %) y R04 (total cobrado faltante o negativo: 1,96 % contra 1,64 %).
- Las reglas de advertencia no sacan filas: 977.379 filas aceptadas de julio 2025 (25,1 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 27,2 %, contra 10,0 % en julio 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de julio 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de julio 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Queens | JFK Airport | 167.832 | 171.063 | -3.231 | -1,89 |
| Manhattan | Midtown Center | 165.567 | 152.360 | 13.207 | 8,67 |
| Manhattan | Upper East Side South | 140.124 | 125.888 | 14.236 | 11,31 |
| Manhattan | Penn Station/Madison Sq West | 123.100 | 103.653 | 19.447 | 18,76 |
| Manhattan | Midtown East | 117.685 | 110.865 | 6.820 | 6,15 |
| Manhattan | Times Sq/Theatre District | 117.573 | 104.798 | 12.775 | 12,19 |
| Manhattan | Upper East Side North | 115.557 | 107.793 | 7.764 | 7,20 |
| Manhattan | Murray Hill | 101.795 | 92.693 | 9.102 | 9,82 |
| Manhattan | East Chelsea | 95.929 | 84.687 | 11.242 | 13,27 |
| Manhattan | Lincoln Square East | 94.771 | 86.918 | 7.853 | 9,03 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +6,2 % en Midtown East y +18,8 % en Penn Station/Madison Sq West) y una cae (JFK Airport −1,9 %). JFK Airport lidera con 167.832 viajes (−1,9 %). Respecto de julio 2024 entra al top 10 East Chelsea y sale LaGuardia Airport. En los aeropuertos, JFK (puesto 1 del top) cae −1,9 % y LaGuardia (fuera del top) cae −5,0 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 34,0 % de los pickups, frente al 38,8 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (8.673 → 32.835), aunque sobre una base chica, contra +22,4 % del total.

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
| 2025 | 7 | 5 | 32.030 | 31,72 |
| 2024 | 7 | 5 | 18.807 | 37,43 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 31,72 en 2025 y US$ 37,43 en 2024. Es una hora de poco volumen (32.030 viajes, contra 235.991 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 16,2 % de sus viajes toca JFK o LaGuardia (contra 8,7 % en todo el mes) y la distancia media es de 5,85 millas (contra 3,63). En 2025 los viajes de aeropuerto son menos (del 25,0 % al 16,2 % de los viajes de las 5:00) y la distancia media baja (de 6,15 a 5,85 millas), por eso el ingreso por viaje cae un 15,3 %.

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
| ALL ZONES |  | 3.648.036 | 2.713.783 | 74,39 |
| Greenwich Village South | Manhattan | 48.602 | 48.529 | 99,85 |
| SoHo | Manhattan | 30.889 | 30.827 | 99,80 |
| West Village | Manhattan | 76.749 | 76.592 | 99,80 |
| Battery Park | Manhattan | 2.110 | 2.105 | 99,76 |
| Midtown Center | Manhattan | 165.567 | 165.127 | 99,73 |

**Interpretación:** El 74,39 % de los viajes de julio 2025 pagó cbd_congestion_fee (2.713.783 de 3.648.036, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, SoHo, West Village, Battery Park y Midtown Center, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En julio 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 51.044 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 7 | 0 | Flex Fare | 800.750 | 1,32 | 1,41 |
| 2025 | 7 | 1 | Credit card | 2.277.584 | 25,13 | 21,71 |
| 2025 | 7 | 2 | Cash | 350.273 | 0,00 | 0,00 |
| 2025 | 7 | 3 | No charge | 13.984 | 0,04 | 0,05 |
| 2025 | 7 | 4 | Dispute | 51.242 | 0,04 | 0,02 |
| 2024 | 7 | 0 | Flex Fare | 262.823 | 3,53 | 3,86 |
| 2024 | 7 | 1 | Credit card | 2.231.217 | 25,10 | 21,54 |
| 2024 | 7 | 2 | Cash | 433.378 | 0,00 | 0,00 |
| 2024 | 7 | 3 | No charge | 13.087 | 0,03 | 0,02 |
| 2024 | 7 | 4 | Dispute | 32.153 | 0,09 | 0,09 |

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 25,13 % de la tarifa en 2025 frente a 25,10 % en 2024 (21,7 % y 21,5 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 9,1 % al 26,2 % de los viajes (262.823 → 800.750 con tarifa > 0) y cuya propina cae del 3,53 % al 1,32 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 10,0 % al 27,2 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,8 % al 62,4 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 7 | 317.958 | 56,04 | 193.486 | 128.353 |
| 2024 | 7 | 329.146 | 56,28 | 199.006 | 134.918 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 3,4 % (329.146 → 317.958) mientras el total de la ciudad sube un 22,4 %, así que su peso cae del 11,0 % al 8,7 % de los viajes. Por aeropuerto, JFK cae −2,8 % y LaGuardia cae −4,9 %. La tarifa promedio se mantiene (US$ 56,28 → US$ 56,04), y la mediana baja de US$ 56,20 a US$ 55,00. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.648.036 | 2.981.368 | 666.668 | 22,36 | 19,36 | 20,09 | -3,59 |

**Interpretación:**

- Julio 2025 tuvo 3.648.036 viajes válidos contra 2.981.368 en julio 2024: +666.668 viajes (+22,36 %). La recaudación total (total_amount) crece un 18,5 %, de US$ 86,2 M a US$ 102,1 M.
- Parte del salto es de calendario: julio 2025 tuvo 5 jueves (días fuertes), y julio 2024, 5 lunes (días flojos). Con el calendario de 2024 la variación sería +21,9 %. Todos los días de la semana crecen (por día), entre +16 % y +33 %, así que el aumento es real.
- La tarifa promedio baja un 3,59 % (de US$ 20,09 a US$ 19,36). La mediana no cambia (US$ 14,20): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de julio 2025 hay más viajes Flex Fare, que son más baratos (US$ 17,49 contra US$ 20,02 del resto) y pasan del 9 % al 26 % de los viajes, menos viajes a aeropuertos (del 11,0 % al 8,7 %) y menos viajes de más de 10 millas (del 9,1 % al 8,2 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 20,16 a US$ 20,02).
- Calidad: la cuarentena sube del 3,10 % al 6,44 % de las filas leídas (250.927 filas en julio 2025 y 95.535 en julio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,18 % contra 1,57 %) y R04 (total cobrado faltante o negativo: 1,96 % contra 1,64 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en julio 2025 (+22,4 % de viajes, +18,5 % de recaudación). Las zonas que más suman viajes son East Village (+38,0 %), Penn Station/Madison Sq West (+18,8 %) y Union Sq (+18,2 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 74,4 % de los viajes de julio 2025; en julio 2024 todavía no existía, así que no hay comparación directa.
- El viaje promedio es más largo (3,63 contra 3,59 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 14,20, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta no se mueve (25,1 % → 25,1 %).
- Hay 75 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 2.261,20, en 2024) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (julio 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,44 % y del 3,10 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-07 INGEST_MODE=direct WAREHOUSE=duckdb`.
