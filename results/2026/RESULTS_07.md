# Resultados: julio 2026 vs julio 2025

> En julio 2026 los taxis amarillos hicieron 3.346.432 viajes válidos, −8,3 % que en julio 2025 (3.648.036), con una recaudación de US$ 100,8 M (−1,2 %).

| | |
|---|---|
| Comando | `make all MES=2026-07 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-07.parquet` y `yellow_tripdata_2025-07.parquet` |
| Corrida | `20261118T045139Z-b031fa`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=07/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-07 | `yellow_tripdata_2026-07.parquet` | 3.530.109 | 3.530.109 | 3.346.432 | 183.677 | 5,20 % | 889.660 (25,20 %) | sí |
| 2025-07 | `yellow_tripdata_2025-07.parquet` | 3.898.963 | 3.898.963 | 3.648.036 | 250.927 | 6,44 % | 977.379 (25,07 %) | sí |

| regla | severidad | qué controla | 2026-07 | 2025-07 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 46 (0,00 %) | 7 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 42.316 (1,20 %) | 56.064 (1,44 %) | −0,24 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 128.494 (3,64 %) | 124.048 (3,18 %) | +0,46 pp |
| R04 | reject | Total cobrado faltante o negativo. | 14.699 (0,42 %) | 76.455 (1,96 %) | −1,54 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 978.329 (27,71 %) | 1.059.299 (27,17 %) | +0,55 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 1 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 18.784 (0,53 %) | 251.281 (6,44 %) | −5,91 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.148 (0,03 %) | 1.043 (0,03 %) | +0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 9.731 (0,28 %) | 51.044 (1,31 %) | −1,03 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena baja del 6,44 % al 5,20 % de las filas leídas (183.677 filas en julio 2026 y 250.927 en julio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,64 % contra 3,18 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,20 % contra 1,44 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,54 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 889.660 filas aceptadas de julio 2026 (25,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 27,7 %, contra 27,2 % en julio 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de julio 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de julio 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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
| Manhattan | Midtown Center | 146.708 | 165.567 | -18.859 | -11,39 |
| Queens | JFK Airport | 145.712 | 167.832 | -22.120 | -13,18 |
| Manhattan | Upper East Side South | 134.447 | 140.124 | -5.677 | -4,05 |
| Manhattan | Penn Station/Madison Sq West | 113.339 | 123.100 | -9.761 | -7,93 |
| Manhattan | Upper East Side North | 112.612 | 115.557 | -2.945 | -2,55 |
| Manhattan | Midtown East | 108.595 | 117.685 | -9.090 | -7,72 |
| Manhattan | Times Sq/Theatre District | 104.344 | 117.573 | -13.229 | -11,25 |
| Manhattan | Lincoln Square East | 93.340 | 94.771 | -1.431 | -1,51 |
| Manhattan | Murray Hill | 92.657 | 101.795 | -9.138 | -8,98 |
| Manhattan | East Chelsea | 91.616 | 95.929 | -4.313 | -4,50 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan y las diez caen, entre −1,5 % (Lincoln Square East) y −13,2 % (JFK Airport). Midtown Center lidera con 146.708 viajes (−11,4 %) y desplaza a JFK Airport, que encabezaba julio 2025. En los aeropuertos, JFK (puesto 2 del top) cae −13,2 % y LaGuardia (fuera del top) cae −9,0 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−8,3 %). La concentración casi no cambia: el top 10 reúne el 34,2 % de los pickups (34,0 % en 2025). Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (32.835 → 14.479), aunque sobre una base chica, contra −8,3 % del total.

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
| 2026 | 7 | 5 | 32.286 | 33,97 |
| 2025 | 7 | 5 | 32.030 | 31,72 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,97 en 2026 y US$ 31,72 en 2025. Es una hora de poco volumen (32.286 viajes, contra 210.008 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,2 % de sus viajes toca JFK o LaGuardia (contra 8,5 % en todo el mes) y la distancia media es de 5,57 millas (contra 3,57). En 2026 los viajes de aeropuerto son más (del 16,2 % al 18,2 % de los viajes de las 5:00), por eso el ingreso por viaje sube un 7,1 %, aunque la distancia media baja (de 5,85 a 5,57 millas).

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
| ALL ZONES |  | 3.346.432 | 2.582.737 | 77,18 |
| Greenwich Village South | Manhattan | 45.857 | 45.811 | 99,90 |
| West Village | Manhattan | 75.386 | 75.308 | 99,90 |
| East Village | Manhattan | 86.682 | 86.583 | 99,89 |
| SoHo | Manhattan | 28.991 | 28.955 | 99,88 |
| Greenwich Village North | Manhattan | 44.681 | 44.617 | 99,86 |

**Interpretación:** El 77,18 % de los viajes de julio 2026 pagó cbd_congestion_fee (2.582.737 de 3.346.432, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, West Village, East Village, SoHo y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En julio 2025 lo pagaba el 74,39 % de los viajes: la proporción sube +2,8 pp. La regla R10 marcó 9.731 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2026 | 7 | 0 | Flex Fare | 876.775 | 1,42 | 1,31 |
| 2026 | 7 | 1 | Credit card | 2.123.011 | 25,25 | 22,30 |
| 2026 | 7 | 2 | Cash | 327.829 | 0,00 | 0,00 |
| 2026 | 7 | 3 | No charge | 6.296 | 0,01 | 0,01 |
| 2026 | 7 | 4 | Dispute | 10.750 | 0,01 | 0,01 |
| 2025 | 7 | 0 | Flex Fare | 800.750 | 1,32 | 1,41 |
| 2025 | 7 | 1 | Credit card | 2.277.584 | 25,13 | 21,71 |
| 2025 | 7 | 2 | Cash | 350.273 | 0,00 | 0,00 |
| 2025 | 7 | 3 | No charge | 13.984 | 0,04 | 0,05 |
| 2025 | 7 | 4 | Dispute | 51.242 | 0,04 | 0,02 |

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 25,25 % de la tarifa en 2026 frente a 25,13 % en 2025 (22,3 % y 21,7 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. También pesa Flex Fare (payment_type 0, tarifa fija acordada por app), que se mantiene en el 26,2 % de los viajes (800.750 → 876.775 con tarifa > 0) y cuya propina se mantiene en torno al 1,4 %. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 7 | 285.601 | 55,18 | 170.609 | 118.700 |
| 2025 | 7 | 317.958 | 56,04 | 193.486 | 128.353 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 10,2 % (317.958 → 285.601) mientras el total de la ciudad baja un 8,3 %, así que su peso cae del 8,7 % al 8,5 % de los viajes. Por aeropuerto, JFK cae −11,8 % y LaGuardia cae −7,5 %. La tarifa promedio baja de US$ 56,04 a US$ 55,18 (−1,5 %), y la mediana baja de US$ 55,00 a US$ 52,70. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.346.432 | 3.648.036 | -301.604 | -8,27 | 21,05 | 19,36 | 8,73 |

**Interpretación:**

- Julio 2026 tuvo 3.346.432 viajes válidos contra 3.648.036 en julio 2025: −301.604 viajes (−8,27 %). La recaudación total (total_amount) cae un 1,2 %, de US$ 102,1 M a US$ 100,8 M.
- El calendario casi no influye: julio 2026 tuvo 5 viernes (días flojos), y julio 2025, 5 martes. Todos los días de la semana caen (por día), entre −5 % y −13 %, así que la baja es general.
- La tarifa promedio sube un 8,73 % (de US$ 19,36 a US$ 21,05). La mediana pasa de US$ 14,20 a US$ 15,60 (+9,9 %): el cambio de tarifas es general, no solo de la mezcla.
- En la mezcla de julio 2026 hay una proporción estable de Flex Fare (26 %) y menos viajes de más de 10 millas (del 8,2 % al 7,5 %).
- Calidad: la cuarentena baja del 6,44 % al 5,20 % de las filas leídas (183.677 filas en julio 2026 y 250.927 en julio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,64 % contra 3,18 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,20 % contra 1,44 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en julio 2026 (−8,3 % de viajes, −1,2 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,2 %), Midtown Center (−11,4 %) y Times Sq/Theatre District (−11,3 %).
- El peaje de congestión (CBD) alcanza al 77,2 % de los viajes de julio 2026, contra 74,4 % en julio 2025.
- El viaje promedio es más corto (3,57 contra 3,63 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 15,60). La propina con tarjeta no se mueve (25,1 % → 25,2 %).
- Hay 76 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 3.062,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (julio 2026: columna nueva ignorada: request_source). La cuarentena es del 5,20 % y del 6,44 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-07 INGEST_MODE=direct WAREHOUSE=duckdb`.
