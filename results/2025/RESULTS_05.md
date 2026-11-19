# Resultados: mayo 2025 vs mayo 2024

> En mayo 2025 los taxis amarillos hicieron 4.284.351 viajes válidos, +18,1 % que en mayo 2024 (3.628.125), con una recaudación de US$ 120,7 M (+15,1 %).

| | |
|---|---|
| Comando | `make all MES=2025-05 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-05.parquet` y `yellow_tripdata_2024-05.parquet` |
| Corrida | `20261118T045109Z-a39af0`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=05/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-05 | `yellow_tripdata_2025-05.parquet` | 4.591.845 | 4.591.845 | 4.284.351 | 307.494 | 6,70 % | 1.095.990 (23,87 %) | sí |
| 2024-05 | `yellow_tripdata_2024-05.parquet` | 3.723.833 | 3.723.833 | 3.628.125 | 95.708 | 2,57 % | 439.272 (11,80 %) | sí |

| regla | severidad | qué controla | 2025-05 | 2024-05 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 24 (0,00 %) | 33 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 64.272 (1,40 %) | 1.147 (0,03 %) | +1,37 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 141.491 (3,08 %) | 49.945 (1,34 %) | +1,74 pp |
| R04 | reject | Total cobrado faltante o negativo. | 112.544 (2,45 %) | 48.992 (1,32 %) | +1,14 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 1.220.143 (26,57 %) | 444.414 (11,93 %) | +14,64 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 329.913 (7,18 %) | 64.398 (1,73 %) | +5,46 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.268 (0,03 %) | 1.158 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 52.625 (1,15 %) | 0 (0,00 %) | +1,15 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 2,57 % al 6,70 % de las filas leídas (307.494 filas en mayo 2025 y 95.708 en mayo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,08 % contra 1,34 %) y R04 (total cobrado faltante o negativo: 2,45 % contra 1,32 %).
- Las reglas de advertencia no sacan filas: 1.095.990 filas aceptadas de mayo 2025 (23,9 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 26,6 %, contra 11,9 % en mayo 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de mayo 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de mayo 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 196.106 | 180.307 | 15.799 | 8,76 |
| Queens | JFK Airport | 176.723 | 157.796 | 18.927 | 11,99 |
| Manhattan | Midtown Center | 174.894 | 171.051 | 3.843 | 2,25 |
| Manhattan | Upper East Side North | 172.121 | 165.814 | 6.307 | 3,80 |
| Manhattan | Lincoln Square East | 129.721 | 122.681 | 7.040 | 5,74 |
| Manhattan | Times Sq/Theatre District | 129.165 | 118.198 | 10.967 | 9,28 |
| Manhattan | Midtown East | 125.584 | 122.915 | 2.669 | 2,17 |
| Manhattan | Penn Station/Madison Sq West | 123.140 | 111.827 | 11.313 | 10,12 |
| Queens | LaGuardia Airport | 119.963 | 124.112 | -4.149 | -3,34 |
| Manhattan | Union Sq | 112.686 | 95.313 | 17.373 | 18,23 |

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +2,2 % en Midtown East y +18,2 % en Union Sq) y una cae (LaGuardia Airport −3,3 %). Upper East Side South lidera con 196.106 viajes (+8,8 %). Respecto de mayo 2024 entra al top 10 Union Sq y sale Midtown North. En los aeropuertos, JFK (puesto 2 del top) crece +12,0 % y LaGuardia (puesto 9 del top) cae −3,3 %: los dos quedan por debajo del total de la ciudad (+18,1 %). La demanda además se reparte más: el top 10 concentra el 34,1 % de los pickups, frente al 38,0 % de 2024. Fuera de Manhattan, Brooklyn más que triplica sus pickups (51.409 → 163.936), contra +18,1 % del total.

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
| 2025 | 5 | 5 | 34.116 | 33,20 |
| 2024 | 5 | 5 | 22.545 | 36,10 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,20 en 2025 y US$ 36,10 en 2024. Es una hora de poco volumen (34.116 viajes, contra 285.556 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,3 % de sus viajes toca JFK o LaGuardia (contra 8,7 % en todo el mes) y la distancia media es de 5,97 millas (contra 3,55). En 2025 los viajes de aeropuerto son menos (del 22,5 % al 18,3 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 8,0 %.

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
| ALL ZONES |  | 4.284.351 | 3.137.100 | 73,22 |
| SoHo | Manhattan | 37.285 | 37.233 | 99,86 |
| Greenwich Village South | Manhattan | 61.901 | 61.805 | 99,84 |
| West Village | Manhattan | 92.950 | 92.785 | 99,82 |
| Little Italy/NoLiTa | Manhattan | 47.345 | 47.258 | 99,82 |
| Greenwich Village North | Manhattan | 60.629 | 60.503 | 99,79 |

**Interpretación:** El 73,22 % de los viajes de mayo 2025 pagó cbd_congestion_fee (3.137.100 de 4.284.351, siempre US$ 0,75). Las cinco zonas con mayor proporción (SoHo, Greenwich Village South, West Village, Little Italy/NoLiTa y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En mayo 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 52.625 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 5 | 0 | Flex Fare | 877.068 | 1,70 | 1,85 |
| 2025 | 5 | 1 | Credit card | 2.764.975 | 25,36 | 22,20 |
| 2025 | 5 | 2 | Cash | 382.959 | 0,00 | 0,00 |
| 2025 | 5 | 3 | No charge | 15.145 | 0,11 | 0,15 |
| 2025 | 5 | 4 | Dispute | 51.172 | 0,05 | 0,05 |
| 2024 | 5 | 0 | Flex Fare | 385.532 | 3,16 | 3,25 |
| 2024 | 5 | 1 | Credit card | 2.705.074 | 24,90 | 22,13 |
| 2024 | 5 | 2 | Cash | 480.630 | 0,00 | 0,00 |
| 2024 | 5 | 3 | No charge | 12.650 | 0,05 | 0,03 |
| 2024 | 5 | 4 | Dispute | 31.248 | 0,04 | 0,05 |

**Interpretación:** Con tarjeta de crédito la propina sube: 25,36 % de la tarifa en 2025 frente a 24,90 % en 2024 (22,2 % y 22,1 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,0 % al 25,0 % de los viajes (385.532 → 877.068 con tarifa > 0) y cuya propina cae del 3,16 % al 1,70 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 11,9 % al 26,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,6 % al 64,5 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 5 | 372.036 | 57,27 | 212.939 | 162.577 |
| 2024 | 5 | 357.414 | 56,18 | 194.177 | 166.986 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia suben un 4,1 % (357.414 → 372.036) mientras el total de la ciudad sube un 18,1 %, así que su peso cae del 9,9 % al 8,7 % de los viajes. Por aeropuerto, JFK crece +9,7 % y LaGuardia cae −2,6 %. La tarifa promedio sube de US$ 56,18 a US$ 57,27 (+1,9 %), y la mediana sube de US$ 56,20 a US$ 58,00. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 4.284.351 | 3.628.125 | 656.226 | 18,09 | 19,29 | 20,07 | -3,85 |

**Interpretación:**

- Mayo 2025 tuvo 4.284.351 viajes válidos contra 3.628.125 en mayo 2024: +656.226 viajes (+18,09 %). La recaudación total (total_amount) crece un 15,1 %, de US$ 104,9 M a US$ 120,7 M.
- El calendario casi no influye: mayo 2025 tuvo 5 sábados (días fuertes), y mayo 2024, 5 miércoles (días fuertes). Todos los días de la semana crecen (por día), entre +14 % y +24 %, así que el aumento es real.
- La tarifa promedio baja un 3,85 % (de US$ 20,07 a US$ 19,29). La mediana no cambia (US$ 14,20): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de mayo 2025 hay más viajes Flex Fare, que son más baratos (US$ 16,63 contra US$ 20,17 del resto) y pasan del 11 % al 25 % de los viajes y menos viajes a aeropuertos (del 9,9 % al 8,7 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 19,95 a US$ 20,17). El viaje promedio es más largo: 3,55 contra 3,43 millas.
- Calidad: la cuarentena sube del 2,57 % al 6,70 % de las filas leídas (307.494 filas en mayo 2025 y 95.708 en mayo 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,08 % contra 1,34 %) y R04 (total cobrado faltante o negativo: 2,45 % contra 1,32 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en mayo 2025 (+18,1 % de viajes, +15,1 % de recaudación). Las zonas que más suman viajes son East Village (+34,5 %), JFK Airport (+12,0 %) y Union Sq (+18,2 %), mientras los aeropuertos quedan por debajo del total.
- El peaje de congestión (CBD) alcanza al 73,2 % de los viajes de mayo 2025. Las zonas con mayor proporción de cobro también crecen en viajes (SoHo +25,7 %, Greenwich Village South +24,2 % y West Village +13,9 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,55 contra 3,43 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 14,20, así que el cambio viene de la mezcla de viajes (más Flex Fare y menos aeropuertos). La propina con tarjeta sube (24,9 % → 25,4 %).
- Hay 47 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 998,00, en 2024) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (mayo 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,70 % y del 2,57 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-05 INGEST_MODE=direct WAREHOUSE=duckdb`.
