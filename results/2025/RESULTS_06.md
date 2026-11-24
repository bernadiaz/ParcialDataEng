# Resultados: junio 2025 vs junio 2024

> En junio 2025 los taxis amarillos hicieron 4.050.910 viajes válidos, +17,7 % que en junio 2024 (3.440.443), con una recaudación de US$ 115,1 M (+17,1 %).

**Respaldo en Superset:** [E0.1 Viajes válidos del mes][E0.1] · [E0.2 Viajes válidos, mismo mes del año anterior][E0.2] · [E0.3 Variación de viajes (%)][E0.3] · [E0.4 Recaudación del mes (USD)][E0.4] · [E0.6 Variación de la recaudación (%)][E0.6]

| | |
|---|---|
| Comando | `make all MES=2025-06 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-06.parquet` y `yellow_tripdata_2024-06.parquet` |
| Tablero de respaldo | [`respaldo-local-2025-06`](http://localhost:8090/superset/dashboard/respaldo-local-2025-06/) en Superset |
| Los 12 meses del año | [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/) en Superset |
| Corrida | `20261124T015201Z-299545`, 2026-11-24 01:53 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope. Cada bloque termina con los charts de Superset que muestran sus cifras; la última sección dice cómo se comprobó.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=06/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-06 | `yellow_tripdata_2025-06.parquet` | 4.322.960 | 4.322.960 | 4.050.910 | 272.050 | 6,29 % | 1.143.555 (26,45 %) | sí |
| 2024-06 | `yellow_tripdata_2024-06.parquet` | 3.539.193 | 3.539.193 | 3.440.443 | 98.750 | 2,79 % | 437.566 (12,36 %) | sí |

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1]

| regla | severidad | qué controla | 2025-06 | 2024-06 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 20 (0,00 %) | 51 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 68.583 (1,59 %) | 1.140 (0,03 %) | +1,55 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 135.160 (3,13 %) | 53.123 (1,50 %) | +1,63 pp |
| R04 | reject | Total cobrado faltante o negativo. | 74.257 (1,72 %) | 48.795 (1,38 %) | +0,34 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.235.737 (28,59 %) | 446.620 (12,62 %) | +15,97 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 280.005 (6,48 %) | 66.115 (1,87 %) | +4,61 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.522 (0,04 %) | 1.115 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 49.930 (1,15 %) | 0 (0,00 %) | +1,15 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

**Respaldo en Superset:** [EC.2 Filas que violan cada regla de calidad][EC.2]

- La cuarentena sube del 2,79 % al 6,29 % de las filas leídas (272.050 filas en junio 2025 y 98.750 en junio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,13 % contra 1,50 %) y R04 (total cobrado faltante o negativo: 1,72 % contra 1,38 %).
- Las reglas de advertencia no sacan filas: 1.143.555 filas aceptadas de junio 2025 (26,5 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 28,6 %, contra 12,6 % en junio 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

**Respaldo en Superset:** [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

- Esquema de junio 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de junio 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Queens | JFK Airport | 170.532 | 152.054 | 18.478 | 12,15 |
| Manhattan | Upper East Side South | 169.806 | 156.485 | 13.321 | 8,51 |
| Manhattan | Midtown Center | 168.094 | 159.309 | 8.785 | 5,51 |
| Manhattan | Upper East Side North | 147.490 | 140.804 | 6.686 | 4,75 |
| Manhattan | Midtown East | 122.379 | 118.054 | 4.325 | 3,66 |
| Manhattan | Penn Station/Madison Sq West | 121.977 | 108.725 | 13.252 | 12,19 |
| Manhattan | Times Sq/Theatre District | 121.466 | 113.368 | 8.098 | 7,14 |
| Manhattan | Lincoln Square East | 108.997 | 105.071 | 3.926 | 3,74 |
| Queens | LaGuardia Airport | 108.948 | 112.954 | -4.006 | -3,55 |
| Manhattan | Murray Hill | 108.371 | 101.299 | 7.072 | 6,98 |

**Respaldo en Superset:** [E1.1 Top 10 de zonas de pickup del mes][E1.1]

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +3,7 % en Midtown East y +12,2 % en Penn Station/Madison Sq West) y una cae (LaGuardia Airport −3,5 %). JFK Airport lidera con 170.532 viajes (+12,2 %) y desplaza a Midtown Center, que encabezaba junio 2024. En los aeropuertos, JFK (puesto 1 del top) crece +12,2 % y LaGuardia (puesto 9 del top) cae −3,5 %: los dos quedan por debajo del total de la ciudad (+17,7 %). La demanda además se reparte más: el top 10 concentra el 33,3 % de los pickups, frente al 36,9 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (10.331 → 33.860), aunque sobre una base chica, contra +17,7 % del total.

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
| 2025 | 6 | 5 | 33.295 | 32,56 |
| 2024 | 6 | 5 | 21.168 | 37,77 |

**Respaldo en Superset:** [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 32,56 en 2025 y US$ 37,77 en 2024. Es una hora de poco volumen (33.295 viajes, contra 263.870 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 16,1 % de sus viajes toca JFK o LaGuardia (contra 8,6 % en todo el mes) y la distancia media es de 5,78 millas (contra 3,61). En 2025 los viajes de aeropuerto son menos (del 24,8 % al 16,1 % de los viajes de las 5:00) y la distancia media baja (de 6,16 a 5,78 millas), por eso el ingreso por viaje cae un 13,8 %. Ojo con el tercer puesto de 2025 (las 14:00, US$ 30,80): es artificial, porque lo infla un viaje con una tarifa de US$ 325.478,05. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 29,40.

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
| ALL ZONES |  | 4.050.910 | 2.987.370 | 73,75 |
| Greenwich Village South | Manhattan | 56.768 | 56.660 | 99,81 |
| West Village | Manhattan | 88.064 | 87.893 | 99,81 |
| SoHo | Manhattan | 33.903 | 33.830 | 99,78 |
| Greenwich Village North | Manhattan | 54.712 | 54.593 | 99,78 |
| Union Sq | Manhattan | 106.064 | 105.812 | 99,76 |

**Respaldo en Superset:** [E3.1 Peaje CBD: proporción de viajes, cobro y efecto del inicio][E3.1] · [E3.3 Las 5 zonas con mayor proporción de viajes con peaje][E3.3]

**Interpretación:** El 73,75 % de los viajes de junio 2025 pagó cbd_congestion_fee (2.987.370 de 4.050.910, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, West Village, SoHo, Greenwich Village North y Union Sq, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En junio 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 49.930 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 6 | 0 | Flex Fare | 936.118 | 1,49 | 1,49 |
| 2025 | 6 | 1 | Credit card | 2.517.597 | 25,25 | 22,13 |
| 2025 | 6 | 2 | Cash | 351.739 | 0,00 | 0,00 |
| 2025 | 6 | 3 | No charge | 14.062 | 0,07 | 0,11 |
| 2025 | 6 | 4 | Dispute | 48.613 | 0,03 | 0,02 |
| 2025 | 6 | 5 | Unknown | 1 | 0,00 | 0,00 |
| 2024 | 6 | 0 | Flex Fare | 387.216 | 3,02 | 3,12 |
| 2024 | 6 | 1 | Credit card | 2.547.507 | 24,70 | 22,01 |
| 2024 | 6 | 2 | Cash | 448.459 | 0,00 | 0,00 |
| 2024 | 6 | 3 | No charge | 12.741 | 0,08 | 0,02 |
| 2024 | 6 | 4 | Dispute | 31.023 | 0,08 | 0,08 |

**Respaldo en Superset:** [E4.1 Propina como % de la tarifa, por forma de pago][E4.1]

**Interpretación:** Con tarjeta de crédito la propina sube: 25,25 % de la tarifa en 2025 frente a 24,70 % en 2024 (22,1 % y 22,0 % ponderada), y deja propina el 93 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,6 % al 27,6 % de los viajes (387.216 → 936.118 con tarifa > 0) y cuya propina cae del 3,02 % al 1,49 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 12,6 % al 28,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,0 % al 62,1 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 6 | 346.603 | 57,75 | 202.051 | 148.720 |
| 2024 | 6 | 334.782 | 56,24 | 185.088 | 154.149 |

**Respaldo en Superset:** [E5.1 Viajes y tarifas de los aeropuertos][E5.1]

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia suben un 3,5 % (334.782 → 346.603) mientras el total de la ciudad sube un 17,7 %, así que su peso cae del 9,7 % al 8,6 % de los viajes. Por aeropuerto, JFK crece +9,2 % y LaGuardia cae −3,5 %. La tarifa promedio sube de US$ 56,24 a US$ 57,75 (+2,7 %), pero esa suba está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 325.478,05 (de Midtown Center a JFK Airport, 20,6 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 56,22 a US$ 56,78 (+1,0 %), y la mediana sube de US$ 55,50 a US$ 56,90. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 4.050.910 | 3.440.443 | 610.467 | 17,74 | 19,70 | 19,86 | -0,79 |

**Respaldo en Superset:** [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]

**Interpretación:**

- Junio 2025 tuvo 4.050.910 viajes válidos contra 3.440.443 en junio 2024: +610.467 viajes (+17,74 %). La recaudación total (total_amount) crece un 17,1 %, de US$ 98,3 M a US$ 115,1 M.
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- El calendario juega en contra de junio 2025: junio 2025 tuvo 5 lunes (días flojos), y junio 2024, 5 sábados (días fuertes). Con el calendario de 2024 la variación sería +18,6 %. Todos los días de la semana crecen (por día), entre +11 % y +27 %, así que el aumento es real.
  - _Respaldo:_ [E6.2 Efecto calendario: días de la semana de cada mes][E6.2] · [E6.1 Viajes, recaudación, calendario y tarifas][E6.1]
- La tarifa promedio baja un 0,79 % (de US$ 19,86 a US$ 19,70); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 325.478) la baja es del 1,2 % (de US$ 19,86 a US$ 19,62). La mediana pasa de US$ 14,20 a US$ 14,65 (+3,2 %).
  - _Respaldo:_ [E6.1 Viajes, recaudación, calendario y tarifas][E6.1] · [E5.4 Las tarifas más altas de cada mes (mayores a US$ 500)][E5.4]
- En la mezcla de junio 2025 hay más viajes Flex Fare, que son más baratos (US$ 18,51 contra US$ 20,04 del resto) y pasan del 12 % al 28 % de los viajes y menos viajes a aeropuertos (del 9,7 % al 8,6 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 19,77 a US$ 20,04). El viaje promedio es más largo: 3,61 contra 3,42 millas.
  - _Respaldo:_ [E6.5 Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia][E6.5]
- Calidad: la cuarentena sube del 2,79 % al 6,29 % de las filas leídas (272.050 filas en junio 2025 y 98.750 en junio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,13 % contra 1,50 %) y R04 (total cobrado faltante o negativo: 1,72 % contra 1,38 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.
  - _Respaldo:_ [EC.1 Reconciliación: leídas = aceptadas + cuarentena][EC.1] · [EC.2 Filas que violan cada regla de calidad][EC.2]

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en junio 2025 (+17,7 % de viajes, +17,1 % de recaudación). Las zonas que más suman viajes son East Village (+28,0 %), JFK Airport (+12,2 %) y Upper East Side South (+8,5 %), mientras los aeropuertos quedan por debajo del total.
  - _Respaldo:_ [C1.1 Demanda: viajes y recaudación][C1.1] · [C1.2 Las 10 zonas que más mueven el total][C1.2] · [C1.3 Aeropuertos contra el total de la ciudad][C1.3]
- El peaje de congestión (CBD) alcanza al 73,7 % de los viajes de junio 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Greenwich Village South +12,1 %, West Village +7,3 % y SoHo +13,8 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
  - _Respaldo:_ [C2.1 Alcance del peaje CBD en los dos meses][C2.1] · [C2.2 Zonas con mayor cobro: proporción y variación de sus viajes][C2.2]
- El viaje promedio es más largo (3,61 contra 3,42 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 14,65). La propina con tarjeta sube (24,7 % → 25,3 %).
  - _Respaldo:_ [C3.1 Perfil del viaje: distancia, tarifa, mezcla y propina][C3.1]
- Los promedios son frágiles: 51 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 325.478,05, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
  - _Respaldo:_ [C4.1 Peso de las tarifas atípicas en los promedios][C4.1] · [C4.2 Los viajes con las tarifas más altas][C4.2] · [E2.1 Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos][E2.1]
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (junio 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,29 % y del 2,79 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-06 INGEST_MODE=direct WAREHOUSE=duckdb`.
  - _Respaldo:_ [C5.1 Cuarentena y reconciliación][C5.1] · [C5.2 Cambios de formato de los archivos][C5.2]

## Respaldo en Superset

Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas mismas tablas. Tablero de este mes: [`respaldo-local-2025-06`](http://localhost:8090/superset/dashboard/respaldo-local-2025-06/). Los 12 meses de 2025 contra 2024: [`respaldo-local-2025`](http://localhost:8090/superset/dashboard/respaldo-local-2025/). Los enlaces funcionan con el stack levantado (`docker compose up -d`).

**Auditoría de las cifras:** 331 números en este reporte, 331 se ven en los charts que cita su bloque y 0 no. Las respuestas de `sql/q1..q6` coinciden con la evidencia.

<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->
**Verificación contra Superset:** coincide (2026-11-24 02:18 UTC, corrida `20261124T021601Z-5b0c2e`).

- Tablero `respaldo-local-2025-06`: 54 de 54 charts devolvieron por la API exactamente los datos de este reporte (4.676 celdas comparadas).
- Tablero `respaldo-local-2025`: 17 de 17 charts (6.072 celdas).
- Números de este reporte: 331 de 331 se ven en los charts que cita su bloque.
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
| Resumen | 4.050.910 | E0.1 | `valor_mes` · Viajes válidos |
| Resumen | +17,7 | E0.3 | `variacion_pct` · Viajes válidos |
| Resumen | 3.440.443 | E0.2 | `valor_anterior` · Viajes válidos |
| Resumen | 115,1 M | E0.4 | `valor_mes` · Recaudación total (total_amount) |
| Resumen | +17,1 | E0.6 | `variacion_pct` · Recaudación total (total_amount) |
| Calidad | 4.322.960 | EC.1 | `filas_archivo` · 2025-06 (y 1 más) |
| Calidad | 4.322.960 | EC.1 | `filas_archivo` · 2025-06 (y 1 más) |
| Calidad | 4.050.910 | EC.1 | `aceptadas` · 2025-06 |
| Calidad | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Calidad | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Calidad | 1.143.555 | EC.1 | `con_advertencias` · 2025-06 |
| Calidad | 26,45 | EC.1 | `pct_advertencias` · 2025-06 |
| Calidad | 3.539.193 | EC.1 | `filas_archivo` · 2024-06 (y 1 más) |
| Calidad | 3.539.193 | EC.1 | `filas_archivo` · 2024-06 (y 1 más) |
| Calidad | 3.440.443 | EC.1 | `aceptadas` · 2024-06 |
| Calidad | 98.750 | EC.1 | `cuarentena` · 2024-06 |
| Calidad | 2,79 | EC.1 | `pct_cuarentena` · 2024-06 |
| Calidad | 437.566 | EC.1 | `con_advertencias` · 2024-06 |
| Calidad | 12,36 | EC.1 | `pct_advertencias` · 2024-06 |
| Calidad | 20 | EC.2 | `filas_mes` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 51 | EC.2 | `filas_anterior` · R01 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 68.583 | EC.2 | `filas_mes` · R02 |
| Calidad | 1,59 | EC.2 | `pct_mes` · R02 |
| Calidad | 1.140 | EC.2 | `filas_anterior` · R02 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 1 más) |
| Calidad | +1,55 | EC.2 | `cambio_pp` · R02 |
| Calidad | 135.160 | EC.2 | `filas_mes` · R03 |
| Calidad | 3,13 | EC.2 | `pct_mes` · R03 |
| Calidad | 53.123 | EC.2 | `filas_anterior` · R03 |
| Calidad | 1,50 | EC.2 | `pct_anterior` · R03 |
| Calidad | +1,63 | EC.2 | `cambio_pp` · R03 |
| Calidad | 74.257 | EC.2 | `filas_mes` · R04 |
| Calidad | 1,72 | EC.2 | `pct_mes` · R04 |
| Calidad | 48.795 | EC.2 | `filas_anterior` · R04 |
| Calidad | 1,38 | EC.2 | `pct_anterior` · R04 |
| Calidad | +0,34 | EC.2 | `cambio_pp` · R04 |
| Calidad | 1.235.737 | EC.2 | `filas_mes` · R05 |
| Calidad | 28,59 | EC.2 | `pct_mes` · R05 |
| Calidad | 446.620 | EC.2 | `filas_anterior` · R05 |
| Calidad | 12,62 | EC.2 | `pct_anterior` · R05 |
| Calidad | +15,97 | EC.2 | `cambio_pp` · R05 |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 280.005 | EC.2 | `filas_mes` · R08 |
| Calidad | 6,48 | EC.2 | `pct_mes` · R08 |
| Calidad | 66.115 | EC.2 | `filas_anterior` · R08 |
| Calidad | 1,87 | EC.2 | `pct_anterior` · R08 |
| Calidad | +4,61 | EC.2 | `cambio_pp` · R08 |
| Calidad | 1.522 | EC.2 | `filas_mes` · R09 |
| Calidad | 0,04 | EC.2 | `pct_mes` · R09 |
| Calidad | 1.115 | EC.2 | `filas_anterior` · R09 |
| Calidad | 0,03 | EC.2 | `pct_anterior` · R02 (y 1 más) |
| Calidad | ±0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | 49.930 | EC.2 | `filas_mes` · R10 |
| Calidad | 1,15 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 0,00 | EC.2 | `pct_mes` · R01 (y 15 más) |
| Calidad | +1,15 | EC.2 | `pct_mes` · R10 (y 1 más) |
| Calidad | 2,79 | EC.1 | `pct_cuarentena` · 2024-06 |
| Calidad | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Calidad | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Calidad | 98.750 | EC.1 | `cuarentena` · 2024-06 |
| Calidad | 3,13 | EC.2 | `pct_mes` · R03 |
| Calidad | 1,50 | EC.2 | `pct_anterior` · R03 |
| Calidad | 1,72 | EC.2 | `pct_mes` · R04 |
| Calidad | 1,38 | EC.2 | `pct_anterior` · R04 |
| Calidad | 1.143.555 | EC.1 | `con_advertencias` · 2025-06 |
| Calidad | 26,5 | EC.1 | `pct_advertencias` · 2025-06 |
| Calidad | 28,6 | EC.2 | `pct_mes` · R05 |
| Calidad | 12,6 | EC.2 | `pct_anterior` · R05 |
| Pregunta 1 | 170.532 | E1.1 | `viajes_mes` · JFK Airport Queens |
| Pregunta 1 | 152.054 | E1.1 | `viajes_anterior` · JFK Airport Queens |
| Pregunta 1 | 18.478 | E1.1 | `variacion` · JFK Airport Queens |
| Pregunta 1 | 12,15 | E1.1 | `variacion_pct` · JFK Airport Queens |
| Pregunta 1 | 169.806 | E1.1 | `viajes_mes` · Upper East Side South Manhattan |
| Pregunta 1 | 156.485 | E1.1 | `viajes_anterior` · Upper East Side South Manhattan |
| Pregunta 1 | 13.321 | E1.1 | `variacion` · Upper East Side South Manhattan |
| Pregunta 1 | 8,51 | E1.1 | `variacion_pct` · Upper East Side South Manhattan |
| Pregunta 1 | 168.094 | E1.1 | `viajes_mes` · Midtown Center Manhattan |
| Pregunta 1 | 159.309 | E1.1 | `viajes_anterior` · Midtown Center Manhattan |
| Pregunta 1 | 8.785 | E1.1 | `variacion` · Midtown Center Manhattan |
| Pregunta 1 | 5,51 | E1.1 | `variacion_pct` · Midtown Center Manhattan |
| Pregunta 1 | 147.490 | E1.1 | `viajes_mes` · Upper East Side North Manhattan |
| Pregunta 1 | 140.804 | E1.1 | `viajes_anterior` · Upper East Side North Manhattan |
| Pregunta 1 | 6.686 | E1.1 | `variacion` · Upper East Side North Manhattan |
| Pregunta 1 | 4,75 | E1.1 | `variacion_pct` · Upper East Side North Manhattan |
| Pregunta 1 | 122.379 | E1.1 | `viajes_mes` · Midtown East Manhattan |
| Pregunta 1 | 118.054 | E1.1 | `viajes_anterior` · Midtown East Manhattan |
| Pregunta 1 | 4.325 | E1.1 | `variacion` · Midtown East Manhattan |
| Pregunta 1 | 3,66 | E1.1 | `variacion_pct` · Midtown East Manhattan |
| Pregunta 1 | 121.977 | E1.1 | `viajes_mes` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 108.725 | E1.1 | `viajes_anterior` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 13.252 | E1.1 | `variacion` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 12,19 | E1.1 | `variacion_pct` · Penn Station/Madison Sq West Manhattan |
| Pregunta 1 | 121.466 | E1.1 | `viajes_mes` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 113.368 | E1.1 | `viajes_anterior` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 8.098 | E1.1 | `variacion` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 7,14 | E1.1 | `variacion_pct` · Times Sq/Theatre District Manhattan |
| Pregunta 1 | 108.997 | E1.1 | `viajes_mes` · Lincoln Square East Manhattan |
| Pregunta 1 | 105.071 | E1.1 | `viajes_anterior` · Lincoln Square East Manhattan |
| Pregunta 1 | 3.926 | E1.1 | `variacion` · Lincoln Square East Manhattan |
| Pregunta 1 | 3,74 | E1.1 | `variacion_pct` · Lincoln Square East Manhattan |
| Pregunta 1 | 108.948 | E1.1 | `viajes_mes` · LaGuardia Airport Queens |
| Pregunta 1 | 112.954 | E1.1 | `viajes_anterior` · LaGuardia Airport Queens |
| Pregunta 1 | -4.006 | E1.1 | `variacion` · LaGuardia Airport Queens |
| Pregunta 1 | -3,55 | E1.1 | `variacion_pct` · LaGuardia Airport Queens |
| Pregunta 1 | 108.371 | E1.1 | `viajes_mes` · Murray Hill Manhattan |
| Pregunta 1 | 101.299 | E1.1 | `viajes_anterior` · Murray Hill Manhattan |
| Pregunta 1 | 7.072 | E1.1 | `variacion` · Murray Hill Manhattan |
| Pregunta 1 | 6,98 | E1.1 | `variacion_pct` · Murray Hill Manhattan |
| Pregunta 1 | +3,7 | E1.1 | `variacion_pct` · Midtown East Manhattan (y 3 más) |
| Pregunta 1 | +12,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 4 más) |
| Pregunta 1 | −3,5 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | 170.532 | E1.1 | `viajes_mes` · JFK Airport Queens (y 2 más) |
| Pregunta 1 | +12,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 4 más) |
| Pregunta 1 | 1 | E1.1 | `puesto_mes` · JFK Airport Queens (y 10 más) |
| Pregunta 1 | +12,2 | E1.1 | `variacion_pct` · JFK Airport Queens (y 4 más) |
| Pregunta 1 | 9 | E1.1 | `variacion_pct` · Upper East Side South Manhattan (y 8 más) |
| Pregunta 1 | −3,5 | E1.1 | `variacion_pct` · LaGuardia Airport Queens (y 2 más) |
| Pregunta 1 | +17,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 1 | 33,3 | E1.4 | `valor_mes` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 36,9 | E1.4 | `valor_anterior` · Pickups que concentra el top 10 de cada mes |
| Pregunta 1 | 10.331 | E1.6 | `viajes_anterior` · Bronx |
| Pregunta 1 | 33.860 | E1.6 | `viajes_mes` · Bronx |
| Pregunta 1 | +17,7 | E1.4 | `variacion_pct` · Pickups de todas las zonas |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 1:00 (y 9 más) |
| Pregunta 2 | 33.295 | E2.1 | `viajes_mes` · 5:00 |
| Pregunta 2 | 32,56 | E2.1 | `ingreso_viaje_mes` · 5:00 |
| Pregunta 2 | 5 | E2.1 | `variacion_ingreso_pct` · 1:00 (y 9 más) |
| Pregunta 2 | 21.168 | E2.1 | `viajes_anterior` · 5:00 |
| Pregunta 2 | 37,77 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 1 más) |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 1:00 (y 12 más) |
| Pregunta 2 | 18:00 | E2.1 | `pct_aeropuerto_anterior` · 6:00 (y 5 más) |
| Pregunta 2 | 5:00 | E2.1 | `variacion_ingreso_pct` · 1:00 (y 12 más) |
| Pregunta 2 | 14:00 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 4 más) |
| Pregunta 2 | 32,56 | E2.1 | `ingreso_viaje_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 37,77 | E2.1 | `ingreso_viaje_anterior` · 5:00 (y 2 más) |
| Pregunta 2 | 33.295 | E2.1 | `viajes_mes` · 5:00 (y 1 más) |
| Pregunta 2 | 263.870 | E2.1 | `viajes_mes` · 18:00 (y 1 más) |
| Pregunta 2 | 16,1 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 8,6 | E2.1 | `pct_aeropuerto_mes` · 12:00 (y 1 más) |
| Pregunta 2 | 5,78 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 3,61 | E2.5 | `valor_mes` · Distancia media |
| Pregunta 2 | 24,8 | E2.1 | `pct_aeropuerto_anterior` · 5:00 |
| Pregunta 2 | 16,1 | E2.1 | `pct_aeropuerto_mes` · 5:00 |
| Pregunta 2 | 6,16 | E2.1 | `distancia_media_anterior` · 5:00 |
| Pregunta 2 | 5,78 | E2.1 | `distancia_media_mes` · 5:00 |
| Pregunta 2 | 13,8 | E2.1 | `variacion_ingreso_pct` · 5:00 (y 1 más) |
| Pregunta 2 | 30,80 | E2.1 | `ingreso_viaje_mes` · 14:00 |
| Pregunta 2 | 325.478,05 | E2.1 | `tarifa_maxima_mes` · 14:00 |
| Pregunta 2 | 29,40 | E2.1 | `ingreso_sin_atipicas_mes` · 14:00 |
| Pregunta 3 | 4.050.910 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 2.987.370 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 73,75 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 56.768 | E3.3 | `viajes` · Greenwich Village South Manhattan |
| Pregunta 3 | 56.660 | E3.3 | `viajes_con_peaje` · Greenwich Village South Manhattan |
| Pregunta 3 | 99,81 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 88.064 | E3.3 | `viajes` · West Village Manhattan |
| Pregunta 3 | 87.893 | E3.3 | `viajes_con_peaje` · West Village Manhattan |
| Pregunta 3 | 99,81 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 1 más) |
| Pregunta 3 | 33.903 | E3.3 | `viajes` · SoHo Manhattan |
| Pregunta 3 | 33.830 | E3.3 | `viajes_con_peaje` · SoHo Manhattan |
| Pregunta 3 | 99,78 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 1 más) |
| Pregunta 3 | 54.712 | E3.3 | `viajes` · Greenwich Village North Manhattan |
| Pregunta 3 | 54.593 | E3.3 | `viajes_con_peaje` · Greenwich Village North Manhattan |
| Pregunta 3 | 99,78 | E3.3 | `pct_con_peaje` · SoHo Manhattan (y 1 más) |
| Pregunta 3 | 106.064 | E3.3 | `viajes` · Union Sq Manhattan |
| Pregunta 3 | 105.812 | E3.3 | `viajes_con_peaje` · Union Sq Manhattan |
| Pregunta 3 | 99,76 | E3.3 | `pct_con_peaje` · Union Sq Manhattan |
| Pregunta 3 | 73,75 | E3.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 2.987.370 | E3.1 | `valor_mes` · Viajes con cbd_congestion_fee > 0 |
| Pregunta 3 | 4.050.910 | E3.1 | `valor_mes` · Viajes válidos (y 2 más) |
| Pregunta 3 | 0,75 | E3.1 | `valor_mes` · Cobro medio (cbd_congestion_fee > 0) (y 1 más) |
| Pregunta 3 | 100 | E3.3 | `pct_con_peaje` · Greenwich Village South Manhattan (y 4 más) |
| Pregunta 3 | 49.930 | E3.5 | `filas_mes` · R10 |
| Pregunta 4 | 936.118 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 1,49 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 1 más) |
| Pregunta 4 | 1,49 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 1 más) |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 6 más) |
| Pregunta 4 | 2.517.597 | E4.1 | `viajes_tarifa_positiva_mes` · Credit card |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 22,13 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash |
| Pregunta 4 | 351.739 | E4.1 | `viajes_tarifa_positiva_mes` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 2 más) |
| Pregunta 4 | 14.062 | E4.1 | `viajes_tarifa_positiva_mes` · No charge |
| Pregunta 4 | 0,07 | E4.1 | `propina_media_pct_mes` · No charge |
| Pregunta 4 | 0,11 | E4.1 | `propina_ponderada_pct_mes` · No charge |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 48.613 | E4.1 | `viajes_tarifa_positiva_mes` · Dispute |
| Pregunta 4 | 0,03 | E4.1 | `propina_media_pct_mes` · Dispute |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 5 | E4.1 | `payment_type` · Unknown |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 6 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 387.216 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 3,02 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 3,12 | E4.1 | `propina_ponderada_pct_anterior` · Flex Fare |
| Pregunta 4 | 1 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 6 más) |
| Pregunta 4 | 2.547.507 | E4.1 | `viajes_tarifa_positiva_anterior` · Credit card |
| Pregunta 4 | 24,70 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,01 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 2 | E4.1 | `payment_type` · Cash |
| Pregunta 4 | 448.459 | E4.1 | `viajes_tarifa_positiva_anterior` · Cash |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 0,00 | E4.1 | `payment_type` · Flex Fare (y 8 más) |
| Pregunta 4 | 3 | E4.1 | `propina_media_pct_anterior` · Flex Fare (y 2 más) |
| Pregunta 4 | 12.741 | E4.1 | `viajes_tarifa_positiva_anterior` · No charge |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,02 | E4.1 | `propina_ponderada_pct_anterior` · No charge (y 1 más) |
| Pregunta 4 | 4 | E4.1 | `payment_type` · Dispute |
| Pregunta 4 | 31.023 | E4.1 | `viajes_tarifa_positiva_anterior` · Dispute |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 0,08 | E4.1 | `propina_media_pct_anterior` · No charge (y 2 más) |
| Pregunta 4 | 25,25 | E4.1 | `propina_media_pct_mes` · Credit card |
| Pregunta 4 | 24,70 | E4.1 | `propina_media_pct_anterior` · Credit card |
| Pregunta 4 | 22,1 | E4.1 | `propina_ponderada_pct_mes` · Credit card |
| Pregunta 4 | 22,0 | E4.1 | `propina_ponderada_pct_anterior` · Credit card |
| Pregunta 4 | 93 | E4.1 | `pct_con_propina_mes` · Credit card |
| Pregunta 4 | 11,6 | E4.1 | `participacion_anterior_pct` · Flex Fare |
| Pregunta 4 | 27,6 | E4.1 | `participacion_mes_pct` · Flex Fare |
| Pregunta 4 | 387.216 | E4.1 | `viajes_tarifa_positiva_anterior` · Flex Fare |
| Pregunta 4 | 936.118 | E4.1 | `viajes_tarifa_positiva_mes` · Flex Fare |
| Pregunta 4 | 3,02 | E4.1 | `propina_media_pct_anterior` · Flex Fare |
| Pregunta 4 | 1,49 | E4.1 | `propina_media_pct_mes` · Flex Fare (y 1 más) |
| Pregunta 4 | 12,6 | E4.4 | `pct_anterior` · R05 |
| Pregunta 4 | 28,6 | E4.4 | `pct_mes` · R05 |
| Pregunta 4 | 74,0 | E4.1 | `participacion_anterior_pct` · Credit card |
| Pregunta 4 | 62,1 | E4.1 | `participacion_mes_pct` · Credit card |
| Pregunta 5 | 346.603 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 57,75 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 202.051 | E5.1 | `valor_mes` · Viajes que tocan JFK |
| Pregunta 5 | 148.720 | E5.1 | `valor_mes` · Viajes que tocan LaGuardia |
| Pregunta 5 | 334.782 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 56,24 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 185.088 | E5.1 | `valor_anterior` · Viajes que tocan JFK |
| Pregunta 5 | 154.149 | E5.1 | `valor_anterior` · Viajes que tocan LaGuardia |
| Pregunta 5 | 3,5 | E5.1 | `variacion_pct` · Viajes que tocan JFK o LaGuardia (y 1 más) |
| Pregunta 5 | 334.782 | E5.1 | `valor_anterior` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 346.603 | E5.1 | `valor_mes` · Viajes que tocan JFK o LaGuardia |
| Pregunta 5 | 17,7 | E5.1 | `variacion_pct` · Viajes válidos |
| Pregunta 5 | 9,7 | E5.1 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 5 | 8,6 | E5.1 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 5 | +9,2 | E5.1 | `variacion_pct` · Viajes que tocan JFK |
| Pregunta 5 | −3,5 | E5.1 | `variacion_pct` · Viajes que tocan LaGuardia |
| Pregunta 5 | 56,24 | E5.1 | `valor_anterior` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 57,75 | E5.1 | `valor_mes` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | +2,7 | E5.1 | `variacion_pct` · Tarifa media de los viajes de aeropuerto |
| Pregunta 5 | 325.478,05 | E5.1 | `valor_mes` · Tarifa máxima de los viajes de aeropuerto (y 1 más) |
| Pregunta 5 | 20,6 | E5.4 | `distancia_millas` · 2025-06 Cash puesto 1 |
| Pregunta 5 | 56,22 | E5.1 | `valor_anterior` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | 56,78 | E5.1 | `valor_mes` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 |
| Pregunta 5 | +1,0 | E5.1 | `variacion_pct` · Tarifa media de aeropuerto sin tarifas mayores a US$ 500 (y 2 más) |
| Pregunta 5 | 55,50 | E5.1 | `valor_anterior` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 56,90 | E5.1 | `valor_mes` · Tarifa mediana de los viajes de aeropuerto |
| Pregunta 5 | 70,00 | E5.1 | `valor_mes` · Tarifa fija de JFK (mediana de RatecodeID 2) (y 1 más) |
| Pregunta 6 | 4.050.910 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.440.443 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | 610.467 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | 17,74 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 19,70 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 19,86 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | -0,79 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 4.050.910 | E6.1 | `valor_mes` · Viajes válidos |
| Pregunta 6 | 3.440.443 | E6.1 | `valor_anterior` · Viajes válidos (y 1 más) |
| Pregunta 6 | +610.467 | E6.1 | `variacion` · Viajes válidos |
| Pregunta 6 | +17,74 | E6.1 | `variacion_pct` · Viajes válidos |
| Pregunta 6 | 17,1 | E6.1 | `variacion_pct` · Recaudación total (total_amount) |
| Pregunta 6 | 98,3 M | E6.1 | `valor_anterior` · Recaudación total (total_amount) |
| Pregunta 6 | 115,1 M | E6.1 | `valor_mes` · Recaudación total (total_amount) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | 5 | E6.2 | `dias_mes` · lunes (y 3 más) |
| Pregunta 6 | +18,6 | E6.1 | `variacion_pct` · Viajes del mes con el calendario del año anterior |
| Pregunta 6 | +11 | E6.2 | `variacion_por_dia_pct` · lunes (y 1 más) |
| Pregunta 6 | +27 | E6.2 | `variacion_por_dia_pct` · domingo |
| Pregunta 6 | 0,79 | E6.1 | `variacion_pct` · Tarifa media |
| Pregunta 6 | 19,86 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,70 | E6.1 | `valor_mes` · Tarifa media |
| Pregunta 6 | 325.478 | E6.1 | `valor_mes` · Tarifa máxima (y 1 más) |
| Pregunta 6 | 1,2 | E6.1 | `variacion_pct` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 19,86 | E6.1 | `valor_anterior` · Tarifa media (y 1 más) |
| Pregunta 6 | 19,62 | E6.1 | `valor_mes` · Tarifa media sin tarifas mayores a US$ 500 |
| Pregunta 6 | 14,20 | E6.1 | `valor_anterior` · Tarifa mediana |
| Pregunta 6 | 14,65 | E6.1 | `valor_mes` · Tarifa mediana |
| Pregunta 6 | +3,2 | E6.1 | `variacion_pct` · Tarifa mediana |
| Pregunta 6 | 18,51 | E6.5 | `valor_mes` · Tarifa media Flex Fare (y 1 más) |
| Pregunta 6 | 20,04 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 12 | E6.5 | `valor_anterior` · Participación de Flex Fare (y 1 más) |
| Pregunta 6 | 28 | E6.5 | `valor_mes` · Participación de Flex Fare |
| Pregunta 6 | 9,7 | E6.5 | `valor_anterior` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 8,6 | E6.5 | `valor_mes` · Participación de los viajes de aeropuerto |
| Pregunta 6 | 19,77 | E6.5 | `valor_anterior` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 20,04 | E6.5 | `valor_mes` · Tarifa media sin Flex Fare ni tarifas mayores a US$ 500 |
| Pregunta 6 | 3,61 | E6.5 | `valor_mes` · Distancia media |
| Pregunta 6 | 3,42 | E6.5 | `valor_anterior` · Distancia media |
| Pregunta 6 | 2,79 | EC.1 | `pct_cuarentena` · 2024-06 |
| Pregunta 6 | 6,29 | EC.1 | `pct_cuarentena` · 2025-06 |
| Pregunta 6 | 272.050 | EC.1 | `cuarentena` · 2025-06 |
| Pregunta 6 | 98.750 | EC.1 | `cuarentena` · 2024-06 |
| Pregunta 6 | 3,13 | EC.2 | `pct_mes` · R03 |
| Pregunta 6 | 1,50 | EC.2 | `pct_anterior` · R03 |
| Pregunta 6 | 1,72 | EC.2 | `pct_mes` · R04 |
| Pregunta 6 | 1,38 | EC.2 | `pct_anterior` · R04 |
| Conclusiones | +17,7 | C1.1 | `variacion_pct` · Viajes válidos |
| Conclusiones | +17,1 | C1.1 | `variacion_pct` · Recaudación total (total_amount) |
| Conclusiones | +28,0 | C1.2 | `variacion_pct` · East Village Manhattan |
| Conclusiones | +12,2 | C1.2 | `variacion_pct` · JFK Airport Queens (y 2 más) |
| Conclusiones | +8,5 | C1.2 | `variacion_pct` · Upper East Side South Manhattan |
| Conclusiones | 73,7 | C2.1 | `valor_mes` · Proporción de viajes con cbd_congestion_fee > 0 |
| Conclusiones | +12,1 | C2.2 | `variacion_viajes_pct` · Greenwich Village South Manhattan |
| Conclusiones | +7,3 | C2.2 | `variacion_viajes_pct` · West Village Manhattan |
| Conclusiones | +13,8 | C2.2 | `variacion_viajes_pct` · SoHo Manhattan |
| Conclusiones | 3,61 | C3.1 | `valor_mes` · Distancia media |
| Conclusiones | 3,42 | C3.1 | `valor_anterior` · Distancia media |
| Conclusiones | 14,20 | C3.1 | `valor_anterior` · Tarifa mediana |
| Conclusiones | 14,65 | C3.1 | `valor_mes` · Tarifa mediana |
| Conclusiones | 24,7 | C3.1 | `valor_anterior` · Propina media con tarjeta de crédito |
| Conclusiones | 25,3 | C3.1 | `valor_mes` · Propina media con tarjeta de crédito |
| Conclusiones | 51 | C4.1 | `valor_mes` · Viajes con tarifa mayor a US$ 500 en los dos meses |
| Conclusiones | 325.478,05 | C4.1 | `valor_mes` · Tarifa máxima (y 2 más) |
| Conclusiones | 6,29 | C5.1 | `pct_cuarentena` · 2025-06 |
| Conclusiones | 2,79 | C5.1 | `pct_cuarentena` · 2024-06 |

</details>

[E0.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-1
[E0.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-2
[E0.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-3
[E0.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-4
[E0.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-5
[E0.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-6
[E0.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-7
[E0.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E0-8
[EC.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-EC-1
[EC.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-EC-2
[EC.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-EC-3
[EC.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-EC-4
[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-1
[E1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-2
[E1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-3
[E1.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-4
[E1.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-5
[E1.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-6
[E1.7]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-7
[E1.8]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E1-8
[E2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E2-1
[E2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E2-2
[E2.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E2-3
[E2.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E2-4
[E2.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E2-5
[E3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E3-1
[E3.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E3-5
[E3.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E3-3
[E3.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E3-4
[E3.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E3-2
[E4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E4-1
[E4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E4-2
[E4.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E4-3
[E4.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E4-4
[E5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E5-1
[E5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E5-2
[E5.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E5-3
[E5.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E5-4
[E6.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-1
[E6.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-2
[E6.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-3
[E6.4]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-4
[E6.5]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-5
[E6.6]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-E6-6
[C1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C1-1
[C1.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C1-2
[C1.3]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C1-3
[C2.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C2-1
[C2.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C2-2
[C3.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C3-1
[C4.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C4-1
[C4.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C4-2
[C5.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C5-1
[C5.2]: http://localhost:8090/superset/dashboard/respaldo-local-2025-06/#CHART-C5-2
