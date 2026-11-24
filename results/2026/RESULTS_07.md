# Resultados: julio 2026 vs julio 2025

> En julio 2026 los taxis amarillos hicieron 3.346.432 viajes válidos, −8,3 % que en julio 2025 (3.648.036), con una recaudación de US$ 100,8 M (−1,2 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2026-07 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2026-07.parquet` y `yellow_tripdata_2025-07.parquet` |
| Tablero de respaldo | [`respaldo-local-2026-07`](http://localhost:8090/superset/dashboard/respaldo-local-2026-07/) en Superset |
| Los 12 meses del año | [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/) en Superset |
| Corrida | `20261124T015350Z-fa7da8`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2026/month=07/` y el mismo camino para 2025, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-07 | `yellow_tripdata_2026-07.parquet` | 3.530.109 | 3.530.109 | 3.346.432 | 183.677 | 5,20 % | 889.660 (25,20 %) | sí |
| 2025-07 | `yellow_tripdata_2025-07.parquet` | 3.898.963 | 3.898.963 | 3.648.036 | 250.927 | 6,44 % | 977.379 (25,07 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

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

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena baja del 6,44 % al 5,20 % de las filas leídas (183.677 filas en julio 2026 y 250.927 en julio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,64 % contra 3,18 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,20 % contra 1,44 %).
- La regla que más cambia es R04 (total cobrado faltante o negativo): −1,54 pp de las filas leídas.
- Las reglas de advertencia no sacan filas: 889.660 filas aceptadas de julio 2026 (25,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 27,7 %, contra 27,2 % en julio 2025).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de julio 2026: el archivo trae columnas nuevas que el contrato no conoce (`request_source`): se ignoran y se reportan, sin romper la carga.
- Esquema de julio 2025: el archivo coincide con el contrato (mismas columnas y tipos).

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

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan y las diez caen, entre −1,5 % (Lincoln Square East) y −13,2 % (JFK Airport). Midtown Center lidera con 146.708 viajes (−11,4 %) y desplaza a JFK Airport, que encabezaba julio 2025. En los aeropuertos, JFK (puesto 2 del top) cae −13,2 % y LaGuardia (fuera del top) cae −9,0 %: JFK va peor que el total de la ciudad y LaGuardia queda en línea con él (−8,3 %). La concentración casi no cambia: el top 10 reúne el 34,2 % de los pickups (34,0 % en 2025). Fuera de Manhattan, el Bronx pierde más de la mitad de sus pickups (32.835 → 14.479), aunque sobre una base chica, contra −8,3 % del total.

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
| 2026 | 7 | 5 | 32.286 | 33,97 |
| 2025 | 7 | 5 | 32.030 | 31,72 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,97 en 2026 y US$ 31,72 en 2025. Es una hora de poco volumen (32.286 viajes, contra 210.008 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,2 % de sus viajes toca JFK o LaGuardia (contra 8,5 % en todo el mes) y la distancia media es de 5,57 millas (contra 3,57). En 2026 los viajes de aeropuerto son más (del 16,2 % al 18,2 % de los viajes de las 5:00), por eso el ingreso por viaje sube un 7,1 %, aunque la distancia media baja (de 5,85 a 5,57 millas).

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
| ALL ZONES |  | 3.346.432 | 2.582.737 | 77,18 |
| Greenwich Village South | Manhattan | 45.857 | 45.811 | 99,90 |
| West Village | Manhattan | 75.386 | 75.308 | 99,90 |
| East Village | Manhattan | 86.682 | 86.583 | 99,89 |
| SoHo | Manhattan | 28.991 | 28.955 | 99,88 |
| Greenwich Village North | Manhattan | 44.681 | 44.617 | 99,86 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 77,18 % de los viajes de julio 2026 pagó cbd_congestion_fee (2.582.737 de 3.346.432, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, West Village, East Village, SoHo y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En julio 2025 lo pagaba el 74,39 % de los viajes: la proporción sube +2,8 pp. La regla R10 marcó 9.731 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 25,25 % de la tarifa en 2026 frente a 25,13 % en 2025 (22,3 % y 21,7 % ponderada), y deja propina el 92 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. También pesa Flex Fare (payment_type 0, tarifa fija acordada por app), que se mantiene en el 26,2 % de los viajes (800.750 → 876.775 con tarifa > 0) y cuya propina se mantiene en torno al 1,4 %. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2026 | 7 | 285.601 | 55,18 | 170.609 | 118.700 |
| 2025 | 7 | 317.958 | 56,04 | 193.486 | 128.353 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 10,2 % (317.958 → 285.601) mientras el total de la ciudad baja un 8,3 %, así que su peso cae del 8,7 % al 8,5 % de los viajes. Por aeropuerto, JFK cae −11,8 % y LaGuardia cae −7,5 %. La tarifa promedio baja de US$ 56,04 a US$ 55,18 (−1,5 %), y la mediana baja de US$ 55,00 a US$ 52,70. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.346.432 | 3.648.036 | -301.604 | -8,27 | 21,05 | 19,36 | 8,73 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Julio 2026 tuvo 3.346.432 viajes válidos contra 3.648.036 en julio 2025: −301.604 viajes (−8,27 %). La recaudación total (total_amount) cae un 1,2 %, de US$ 102,1 M a US$ 100,8 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario casi no influye: julio 2026 tuvo 5 viernes (días flojos), y julio 2025, 5 martes. Todos los días de la semana caen (por día), entre −5 % y −13 %, así que la baja es general.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio sube un 8,73 % (de US$ 19,36 a US$ 21,05). La mediana pasa de US$ 14,20 a US$ 15,60 (+9,9 %): el cambio de tarifas es general, no solo de la mezcla.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de julio 2026 hay una proporción estable de Flex Fare (26 %) y menos viajes de más de 10 millas (del 8,2 % al 7,5 %).
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena baja del 6,44 % al 5,20 % de las filas leídas (183.677 filas en julio 2026 y 250.927 en julio 2025). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,64 % contra 3,18 %) y R02 (dropoff sin fecha, anterior o igual al pickup: 1,20 % contra 1,44 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos cae en forma moderada en julio 2026 (−8,3 % de viajes, −1,2 % de recaudación). Las zonas que más pierden viajes son JFK Airport (−13,2 %), Midtown Center (−11,4 %) y Times Sq/Theatre District (−11,3 %).
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 77,2 % de los viajes de julio 2026, contra 74,4 % en julio 2025.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más corto (3,57 contra 3,63 millas) y más caro sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 15,60). La propina con tarjeta no se mueve (25,1 % → 25,2 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Hay 76 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 3.062,00, en 2026) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (julio 2026: columna nueva ignorada: request_source). La cuarentena es del 5,20 % y del 6,44 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2026-07 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2026-07`](http://localhost:8090/superset/dashboard/respaldo-local-2026-07/). Los 12 meses de 2026 contra 2025: [`respaldo-local-2026`](http://localhost:8090/superset/dashboard/respaldo-local-2026/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 301 números en este reporte, 301 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:25 UTC, corrida `20261124T022142Z-3c2cd6`).

- Tablero `respaldo-local-2026-07`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.690 celdas comparadas).
- Tablero `respaldo-local-2026`: 17 de 17 charts (4.587 celdas).
- Números de este reporte: 301 de 301 se ven en los charts que cita su bloque.
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
| Resumen | 3.346.432 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | −8,3 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.648.036 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 100,8 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | −1,2 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 3.530.109 | EC.1 | `filas_archivo` · 2026-07 (y 1 más) |
| Calidad | 3.530.109 | EC.1 | `filas_archivo` · 2026-07 (y 1 más) |
| Calidad | 3.346.432 | EC.1 | `aceptadas` · 2026-07 |
| Calidad | 183.677 | EC.1 | `cuarentena` · 2026-07 |
| Calidad | 5,20 | EC.1 | `pct_cuarentena` · 2026-07 |
| Calidad | 889.660 | EC.1 | `con_advertencias` · 2026-07 |
| Calidad | 25,20 | EC.1 | `pct_advertencias` · 2026-07 |
| Calidad | 3.898.963 | EC.1 | `filas_archivo` · 2025-07 (y 1 más) |
| Calidad | 3.898.963 | EC.1 | `filas_archivo` · 2025-07 (y 1 más) |
| Calidad | 3.648.036 | EC.1 | `aceptadas` · 2025-07 |
| Calidad | 250.927 | EC.1 | `cuarentena` · 2025-07 |
| Calidad | 6,44 | EC.1 | `pct_cuarentena` · 2025-07 |
| Calidad | 977.379 | EC.1 | `con_advertencias` · 2025-07 |
| Calidad | 25,07 | EC.1 | `pct_advertencias` · 2025-07 |
| Calidad | 46 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 7 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 42.316 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,20 | EC.2 | `pct_mes` · R02 |
| Calidad | 56.064 | EC.2 | `filas_anterior` · R02 |
| Calidad | 1,44 | EC.2 | `pct_anterior` · R02 |
| Calidad | −0,24 | EC.2 | `cambio_pp` · R02 |
| Calidad | 128.494 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,64 | EC.2 | `pct_mes` · R03 |
| Calidad | 124.048 | EC.2 | `filas_anterior` · R03 |
| Calidad | 3,18 | EC.2 | `pct_anterior` · R03 |
| Calidad | +0,46 | EC.2 | `cambio_pp` · R03 |
| Calidad | 14.699 | EC.2 | `filas_mes` · R04 |
| Calidad | 0,42 | EC.2 | `pct_mes` · R04 |
| Calidad | 76.455 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,96 | EC.2 | `pct_anterior` · R04 |
| Calidad | −1,54 | EC.2 | `cambio_pp` · R04 |
| Calidad | 978.329 | EC.2 | `filas_mes` · R05 |
| Calidad | 27,71 | EC.2 | `pct_mes` · R05 |
| Calidad | 1.059.299 | EC.2 | `filas_anterior` · R05 |
| Calidad | 27,17 | EC.2 | `pct_anterior` · R05 |
| Calidad | +0,55 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 1 | EC.2 | `pct_mes` · R02 (y 6 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 11 más) |
| Calidad | 18.784 | EC.2 | `filas_mes` · R08 |
| Calidad | 0,53 | EC.2 | `pct_mes` · R08 |
| Calidad | 251.281 | EC.2 | `filas_anterior` · R08 |
| Calidad | 6,44 | EC.2 | `pct_anterior` · R08 |
| Calidad | −5,91 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.148 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | 1.043 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_mes` · R09 (y 1 más) |
| Calidad | +0,01 | EC.2 | `cambio_pp` · R09 |
| Calidad | 9.731 | EC.2 | `filas_mes` · R10 |
| Calidad | 0,28 | EC.2 | `pct_mes` · R10 |
| Calidad | 51.044 | EC.2 | `filas_anterior` · R10 |
| Calidad | 1,31 | EC.2 | `pct_anterior` · R10 |
| Calidad | −1,03 | EC.2 | `cambio_pp` · R10 |
| Calidad | 6,44 | EC.1 | `pct_cuarentena` · 2025-07 (y 1 más) |
| Calidad | 5,20 | EC.1 | `pct_cuarentena` · 2026-07 |
| Calidad | 183.677 | EC.1 | `cuarentena` · 2026-07 |
| Calidad | 250.927 | EC.1 | `cuarentena` · 2025-07 |
| Calidad | 3,64 | EC.2 | `pct_mes` · R03 |
| Calidad | 3,18 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,20 | EC.2 | `pct_mes` · R02 |
| Calidad | 1,44 | EC.2 | `pct_anterior` · R02 |
| Calidad | −1,54 | EC.2 | `cambio_pp` · R04 |
| Calidad | 889.660 | EC.1 | `con_advertencias` · 2026-07 |
| Calidad | 25,2 | EC.1 | `pct_advertencias` · 2026-07 |
| Calidad | 27,7 | EC.2 | `pct_mes` · R05 |
| Calidad | 27,2 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 146.708 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 165.567 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | -18.859 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | -11,39 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 145.712 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 167.832 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | -22.120 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | -13,18 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 134.447 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 140.124 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | -5.677 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | -4,05 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 113.339 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 123.100 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -9.761 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | -7,93 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 112.612 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 115.557 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | -2.945 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | -2,55 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 108.595 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 117.685 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | -9.090 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | -7,72 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 104.344 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 117.573 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -13.229 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | -11,25 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 93.340 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 94.771 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | -1.431 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | -1,51 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 92.657 | E1.1 | `viajes_mes` · Murray Hill Manhattan |
| Pregunta 1 | 101.795 | E1.1 | `viajes_anterior` · Murray Hill Manhattan |
| Pregunta 1 | -9.138 | E1.1 | `variacion` · Murray Hill Manhattan |
| Pregunta 1 | -8,98 | E1.1 | `variacion_pct` · Murray Hill Manhattan |
| Pregunta 1 | 91.616 | E1.1 | `viajes_mes` · East Chelsea Manhattan |
| Pregunta 1 | 95.929 | E1.1 | `viajes_anterior` · East Chelsea Manhattan |
| Pregunta 1 | -4.313 | E1.1 | `variacion` · East Chelsea Manhattan |
| Pregunta 1 | -4,50 | E1.1 | `variacion_pct` · East Chelsea Manhattan |
| Pregunta 1 | −1,5 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan (y 1 más) |
| Pregunta 1 | −13,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | 146.708 | E1.1 | `viajes_mes` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | −11,4 | E1.1 | `variacion_pct` · Midtown Center Manhattan (y 1 más) |
| Pregunta 1 | 2 | E1.1 | `puesto_anterior` · Midtown Center Manhattan (y 6 más) |
| Pregunta 1 | −13,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | −9,0 | E1.1 | `variacion_pct` · Murray Hill Manhattan (y 2 más) |
| Pregunta 1 | −8,3 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 34,2 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 34,0 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 32.835 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 14.479 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | −8,3 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 15 más) |
| Pregunta 2 | 32.286 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 33,97 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 15 más) |
| Pregunta 2 | 32.030 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 31,72 | E2.1 | `ingreso_viaje_anterior` · 5:00 |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 17 más) |
| Pregunta 2 | 18:00 | E2.1 | `pct_aeropuerto_mes` · 5:00 (y 5 más) |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 0:00 (y 17 más) |
| Pregunta 2 | 33,97 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 31,72 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 32.286 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 210.008 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 18,2 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,5 | E2.1 | `pct_aeropuerto_mes` · 13:00 (y 2 más) |
| Pregunta 2 | 5,57 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,57 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 16,2 | E2.1 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 18,2 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 7,1 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 2 más) |
| Pregunta 2 | 5,85 | E2.1 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 5,57 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 3 | 3.346.432 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 2.582.737 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 77,18 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 45.857 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 45.811 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,90 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 75.386 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 75.308 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,90 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 86.682 | E3.3 | `viajes` · East Village Manhattan |
| Pregunta 3 | 86.583 | E3.3 | `viajes_con_peaje` · East Village Manhattan |
| Pregunta 3 | 99,89 | E3.3 | `pct_con_peaje` · East Village Manhattan |
| Pregunta 3 | 28.991 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 28.955 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,88 | E3.3 | `pct_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 44.681 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 44.617 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,86 | E3.3 | `pct_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 77,18 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 (y 1 más) |
| Pregunta 3 | 2.582.737 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 3.346.432 | E3.1 | `valor_mes` · Viajes válidos (y 1 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 3 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 4 más) |
| Pregunta 3 | 74,39 | E3.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | +2,8 | E3.1 | `variacion` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 9.731 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 876.775 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,42 | E4.1 | `propina_media_pct_mes` · Flex Fare |
| Pregunta 4 | 1,31 | E4.1 | `propina_ponderada_pct_mes` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 2.123.011 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,30 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash |
| Pregunta 4 | 327.829 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge |
| Pregunta 4 | 6.296 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 10.750 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 0,01 | E4.1 | `pct_con_propina_mes` · Cash (y 5 más) |
| Pregunta 4 | 800.750 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 1,32 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,41 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare (y 1 más) |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 5 más) |
| Pregunta 4 | 2.277.584 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 25,13 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 21,71 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash |
| Pregunta 4 | 350.273 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 4 más) |
| Pregunta 4 | 3 | E4.1 | `payment_type` · No charge |
| Pregunta 4 | 13.984 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,04 | E4.1 | `propina_media_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 0,05 | E4.1 | `propina_ponderada_pct_anterior` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 51.242 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,04 | E4.1 | `propina_media_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_anterior` · Dispute |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 25,13 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,3 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 21,7 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 92 | E4.1 | `pct_con_propina_mes` · Credit card (y 1 más) |
| Pregunta 4 | 26,2 | E4.1 | `participacion_mes_pct` · Flex Fare (y 1 más) |
| Pregunta 4 | 800.750 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 876.775 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,4 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 2 más) |
| Pregunta 5 | 285.601 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 55,18 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 170.609 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 118.700 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 317.958 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,04 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 193.486 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 128.353 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 10,2 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 317.958 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 285.601 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 8,3 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 8,7 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,5 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | −11,8 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −7,5 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 56,04 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,18 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | −1,5 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 55,00 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 52,70 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 3.346.432 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.648.036 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | -301.604 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | -8,27 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 21,05 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,36 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 8,73 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 3.346.432 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.648.036 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | −301.604 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | −8,27 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 1,2 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 102,1 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 100,8 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 7 más) |
| Pregunta 6 | 5 | E6.2 | `dias_anterior` · martes (y 7 más) |
| Pregunta 6 | −5 | E6.2 | `variacion_por_dia_pct` · viernes (y 1 más) |
| Pregunta 6 | −13 | E6.2 | `variacion_por_dia_pct` · martes |
| Pregunta 6 | 8,73 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 19,36 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 21,05 | E6.1 | `valor_mes` · Tarifa media (y 1 más) |
| Pregunta 6 | 14,20 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 15,60 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +9,9 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 26 | E6.5 | `valor_mes` · Participación de Flex Fare (y 1 más) |
| Pregunta 6 | 8,2 | E6.5 | `valor_anterior` · Viajes de más de 10 millas |
| Pregunta 6 | 7,5 | E6.5 | `valor_mes` · Viajes de más de 10 millas |
| Pregunta 6 | 6,44 | EC.1 | `pct_cuarentena` · 2025-07 (y 1 más) |
| Pregunta 6 | 5,20 | EC.1 | `pct_cuarentena` · 2026-07 |
| Pregunta 6 | 183.677 | EC.1 | `cuarentena` · 2026-07 |
| Pregunta 6 | 250.927 | EC.1 | `cuarentena` · 2025-07 |
| Pregunta 6 | 3,64 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 3,18 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,20 | EC.2 | `pct_mes` · R02 |
| Pregunta 6 | 1,44 | EC.2 | `pct_anterior` · R02 |
| Conclusiones | −8,3 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | −1,2 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | −13,2 | C1.2 | `variacion_pct` · JFK Airport Queens (y 1 más) |
| Conclusiones | −11,4 | C1.2 | `variacion_pct` · Midtown Center Manhattan |
| Conclusiones | −11,3 | C1.2 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Conclusiones | 77,2 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 74,4 | C2.1 | `valor_anterior` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | 3,57 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,63 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,20 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 15,60 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 25,1 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 25,2 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 76 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 3.062,00 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 5,20 | C5.1 | `pct_cuarentena` · 2026-07 |
| Conclusiones | 6,44 | C5.1 | `pct_cuarentena` · 2025-07 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2026-07/#CHART-C5-2
