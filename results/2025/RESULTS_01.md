# Resultados: enero 2025 vs enero 2024

> En enero 2025 los taxis amarillos hicieron 3.323.437 viajes válidos, +15,8 % que en enero 2024 (2.870.896), con una recaudación de US$ 88,3 M (+12,7 %).

| | |
|---|---|
| Comando | `make all MES=2025-01` |
| Modo | nube: Airbyte lleva la tabla de zonas y los archivos mensuales se copian sin cambios de la TLC a S3 (INGEST_MODE=hybrid), la calidad corre en DuckDB y el warehouse es Snowflake |
| Consultas | marts de dbt en Snowflake |
| Archivos de la TLC | `yellow_tripdata_2025-01.parquet` y `yellow_tripdata_2024-01.parquet` |
| Corrida | `20261119T000959Z-6caedd`, 2026-11-19 00:18 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=01/` y el mismo camino para 2024, la tabla `RAW.YELLOW_QUARANTINE`, además de una copia en `s3://<bucket>/quarantine/yellow/`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-01 | `yellow_tripdata_2025-01.parquet` | 3.475.226 | 3.475.226 | 3.323.437 | 151.789 | 4,37 % | 511.679 (14,72 %) | sí |
| 2024-01 | `yellow_tripdata_2024-01.parquet` | 2.964.624 | 2.964.624 | 2.870.896 | 93.728 | 3,16 % | 150.746 (5,08 %) | sí |

| regla | severidad | qué controla | 2025-01 | 2024-01 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 22 (0,00 %) | 18 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 2.051 (0,06 %) | 870 (0,03 %) | +0,03 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 91.055 (2,62 %) | 60.430 (2,04 %) | +0,58 pp |
| R04 | reject | Total cobrado faltante o negativo. | 63.037 (1,81 %) | 35.504 (1,20 %) | +0,62 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 564.805 (16,25 %) | 171.627 (5,79 %) | +10,46 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 148.413 (4,27 %) | 41.402 (1,40 %) | +2,87 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 982 (0,03 %) | 1.107 (0,04 %) | −0,01 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 6.954 (0,20 %) | 0 (0,00 %) | +0,20 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 3,16 % al 4,37 % de las filas leídas (151.789 filas en enero 2025 y 93.728 en enero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 2,04 %) y R04 (total cobrado faltante o negativo: 1,81 % contra 1,20 %).
- Las reglas de advertencia no sacan filas: 511.679 filas aceptadas de enero 2025 (14,7 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 16,3 %, contra 5,8 % en enero 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de enero 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de enero 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Midtown Center | 163.866 | 140.220 | 23.646 | 16,86 |
| Manhattan | Upper East Side South | 159.330 | 140.160 | 19.170 | 13,68 |
| Manhattan | Upper East Side North | 151.616 | 134.027 | 17.589 | 13,12 |
| Queens | JFK Airport | 134.804 | 138.341 | -3.537 | -2,56 |
| Manhattan | Times Sq/Theatre District | 120.657 | 102.999 | 17.658 | 17,14 |
| Manhattan | Penn Station/Madison Sq West | 115.021 | 102.165 | 12.856 | 12,58 |
| Manhattan | Midtown East | 113.840 | 104.374 | 9.466 | 9,07 |
| Manhattan | Lincoln Square East | 107.540 | 101.847 | 5.693 | 5,59 |
| Manhattan | Upper West Side South | 93.831 | 86.532 | 7.299 | 8,44 |
| Manhattan | Midtown North | 92.702 | 83.711 | 8.991 | 10,74 |

**Interpretación:** Nueve de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +5,6 % en Lincoln Square East y +17,1 % en Times Sq/Theatre District) y una cae (JFK Airport −2,6 %). Midtown Center lidera con 163.866 viajes (+16,9 %). Respecto de enero 2024 entra al top 10 Midtown North y sale LaGuardia Airport. En los aeropuertos, JFK (puesto 4 del top) cae −2,6 % y LaGuardia (fuera del top) cae −1,4 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 37,7 % de los pickups, frente al 39,7 % de 2024. Fuera de Manhattan, Brooklyn casi triplica sus pickups (22.286 → 60.244), aunque sobre una base chica, contra +15,8 % del total.

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
| 2025 | 1 | 5 | 21.233 | 33,64 |
| 2024 | 1 | 5 | 17.490 | 37,54 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 33,64 en 2025 y US$ 37,54 en 2024. Es una hora de poco volumen (21.233 viajes, contra 242.182 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 20,8 % de sus viajes toca JFK o LaGuardia (contra 8,2 % en todo el mes) y la distancia media es de 5,71 millas (contra 3,16). En 2025 los viajes de aeropuerto son menos (del 25,8 % al 20,8 % de los viajes de las 5:00) y la distancia media baja (de 6,23 a 5,71 millas), por eso el ingreso por viaje cae un 10,4 %. Ojo con el segundo puesto de 2025 (las 12:00, US$ 30,68): es artificial, porque lo infla un viaje con una tarifa de US$ 863.372,12. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 25,59.

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
| ALL ZONES |  | 3.323.437 | 2.192.727 | 65,98 |
| Stuy Town/Peter Cooper Village | Manhattan | 5.344 | 4.842 | 90,61 |
| Alphabet City | Manhattan | 7.110 | 6.433 | 90,48 |
| Union Sq | Manhattan | 92.363 | 83.546 | 90,45 |
| Midtown East | Manhattan | 113.840 | 102.890 | 90,38 |
| Midtown Center | Manhattan | 163.866 | 147.299 | 89,89 |

**Interpretación:** El 65,98 % de los viajes de enero 2025 pagó cbd_congestion_fee (2.192.727 de 3.323.437, siempre US$ 0,75). El porcentaje está diluido porque el peaje empezó el 5 de enero: del 1 al 4 (10,4 % de los viajes del mes) casi nadie lo pagó (0,12 %; esos cobros anticipados quedan marcados por la regla R10), y desde el 5 lo paga el 73,6 %. Las cinco zonas con mayor proporción (Stuy Town/Peter Cooper Village, Alphabet City, Union Sq, Midtown East y Midtown Center, alrededor del 90 %) están todas en Manhattan, dentro de la zona de peaje. En enero 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 6.954 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 1 | 0 | Flex Fare | 412.946 | 2,74 | 3,02 |
| 2025 | 1 | 1 | Credit card | 2.423.279 | 26,29 | 22,94 |
| 2025 | 1 | 2 | Cash | 367.786 | 0,00 | 0,00 |
| 2025 | 1 | 3 | No charge | 12.025 | 0,01 | 0,02 |
| 2025 | 1 | 4 | Dispute | 35.497 | 0,03 | 0,02 |
| 2024 | 1 | 0 | Flex Fare | 115.127 | 9,14 | 9,06 |
| 2024 | 1 | 1 | Credit card | 2.297.767 | 26,26 | 22,62 |
| 2024 | 1 | 2 | Cash | 422.562 | 0,00 | 0,00 |
| 2024 | 1 | 3 | No charge | 10.383 | 0,04 | 0,03 |
| 2024 | 1 | 4 | Dispute | 22.680 | 0,03 | 0,02 |

**Interpretación:** Con tarjeta de crédito la propina se mantiene estable: 26,29 % de la tarifa en 2025 frente a 26,26 % en 2024 (22,9 % y 22,6 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 4,1 % al 14,6 % de los viajes (115.127 → 412.946 con tarifa > 0) y cuya propina cae del 9,14 % al 2,74 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 5,8 % al 16,3 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 80,0 % al 72,9 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 1 | 270.966 | 58,03 | 157.420 | 116.346 |
| 2024 | 1 | 276.027 | 55,04 | 162.026 | 117.140 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 1,8 % (276.027 → 270.966) mientras el total de la ciudad sube un 15,8 %, así que su peso cae del 9,6 % al 8,2 % de los viajes. Por aeropuerto, JFK cae −2,8 % y LaGuardia cae −0,7 %. La tarifa promedio sube de US$ 55,04 a US$ 58,03 (+5,4 %), pero esa suba no es real: la produce un solo viaje de 2025 con fare_amount = US$ 863.372,12 (de LaGuardia Airport a Astoria Park, 1,6 millas, pago Dispute). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 55,01 a US$ 54,82 (−0,3 %), y la mediana baja de US$ 53,53 a US$ 52,70. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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
| 3.323.437 | 2.870.896 | 452.541 | 15,76 | 17,73 | 18,47 | -4,00 |

**Interpretación:**

- Enero 2025 tuvo 3.323.437 viajes válidos contra 2.870.896 en enero 2024: +452.541 viajes (+15,76 %). La recaudación total (total_amount) crece un 12,7 %, de US$ 78,4 M a US$ 88,3 M.
- Parte del salto es de calendario: enero 2025 tuvo 5 jueves y 5 viernes (días fuertes), y enero 2024, 5 lunes y 5 martes (días flojos). Con el calendario de 2024 la variación sería +14,7 %. Todos los días de la semana crecen (por día), entre +11 % y +21 %, así que el aumento es real.
- La tarifa promedio baja un 4,00 % (de US$ 18,47 a US$ 17,73); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 863.372) la baja es del 5,4 % (de US$ 18,46 a US$ 17,47). La mediana no cambia (US$ 12,80): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de enero 2025 hay más viajes Flex Fare, que son más baratos (US$ 14,84 contra US$ 17,91 del resto) y pasan del 4 % al 15 % de los viajes, menos viajes a aeropuertos (del 9,6 % al 8,2 %) y menos viajes de más de 10 millas (del 7,8 % al 6,8 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,6 % (de US$ 18,40 a US$ 17,91). El viaje promedio es más corto: 3,16 contra 3,29 millas.
- Calidad: la cuarentena sube del 3,16 % al 4,37 % de las filas leídas (151.789 filas en enero 2025 y 93.728 en enero 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,62 % contra 2,04 %) y R04 (total cobrado faltante o negativo: 1,81 % contra 1,20 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en enero 2025 (+15,8 % de viajes, +12,7 % de recaudación). Las zonas que más suman viajes son Midtown Center (+16,9 %), Upper East Side South (+13,7 %) y Union Sq (+24,1 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 66,0 % de los viajes de enero 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Stuy Town/Peter Cooper Village +56,3 %, Alphabet City +117,2 % y Union Sq +24,1 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más corto (3,16 contra 3,29 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 12,80, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta no se mueve (26,3 % → 26,3 %).
- Los promedios son frágiles: 40 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 863.372,12, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (enero 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,37 % y del 3,16 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en Snowflake y se reproducen con `make all MES=2025-01`.
