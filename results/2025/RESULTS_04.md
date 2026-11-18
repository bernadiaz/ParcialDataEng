# Resultados: abril 2025 vs abril 2024

> En abril 2025 los taxis amarillos hicieron 3.776.409 viajes válidos, +10,2 % que en abril 2024 (3.427.499), con una recaudación de US$ 104,2 M (+8,3 %).

| | |
|---|---|
| Comando | `make all MES=2025-04 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-04.parquet` y `yellow_tripdata_2024-04.parquet` |
| Corrida | `20261118T045106Z-dda14a`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=04/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-04 | `yellow_tripdata_2025-04.parquet` | 3.970.553 | 3.970.553 | 3.776.409 | 194.144 | 4,89 % | 721.657 (18,18 %) | sí |
| 2024-04 | `yellow_tripdata_2024-04.parquet` | 3.514.289 | 3.514.289 | 3.427.499 | 86.790 | 2,47 % | 443.403 (12,62 %) | sí |

| regla | severidad | qué controla | 2025-04 | 2024-04 | cambio |
|---|---|---|---:|---:|---:|
| R01 | reject | Pickup sin fecha o fuera del mes del archivo. | 7 (0,00 %) | 9 (0,00 %) | ±0,00 pp |
| R02 | reject | Dropoff sin fecha, anterior o igual al pickup. | 34.769 (0,88 %) | 1.089 (0,03 %) | +0,84 pp |
| R03 | reject | Distancia faltante, cero o negativa, o mayor al máximo fijado. | 91.745 (2,31 %) | 45.963 (1,31 %) | +1,00 pp |
| R04 | reject | Total cobrado faltante o negativo. | 72.608 (1,83 %) | 43.749 (1,24 %) | +0,58 pp |
| R05 | warning | Cantidad de pasajeros NULL o 0. | 768.831 (19,36 %) | 448.167 (12,75 %) | +6,61 pp |
| R06 | reject | Zona de origen o destino que no existe en el lookup de zonas. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R07 | reject | Duplicado exacto de otra fila del mismo archivo. | 0 (0,00 %) | 0 (0,00 %) | ±0,00 pp |
| R08 | warning | Propina negativa o mayor que la tarifa. | 191.095 (4,81 %) | 61.715 (1,76 %) | +3,06 pp |
| R09 | reject | Velocidad media del viaje mayor al máximo fijado. | 1.095 (0,03 %) | 1.141 (0,03 %) | ±0,00 pp |
| R10 | warning | Peaje CBD negativo, o cobrado antes de que existiera. | 50.646 (1,28 %) | 0 (0,00 %) | +1,28 pp |

Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.

- La cuarentena sube del 2,47 % al 4,89 % de las filas leídas (194.144 filas en abril 2025 y 86.790 en abril 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,31 % contra 1,31 %) y R04 (total cobrado faltante o negativo: 1,83 % contra 1,24 %).
- Las reglas de advertencia no sacan filas: 721.657 filas aceptadas de abril 2025 (18,2 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 19,4 %, contra 12,8 % en abril 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de abril 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de abril 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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
| Manhattan | Upper East Side South | 178.609 | 162.264 | 16.345 | 10,07 |
| Manhattan | Midtown Center | 175.894 | 160.322 | 15.572 | 9,71 |
| Manhattan | Upper East Side North | 156.358 | 149.735 | 6.623 | 4,42 |
| Queens | JFK Airport | 145.700 | 148.949 | -3.249 | -2,18 |
| Manhattan | Times Sq/Theatre District | 127.528 | 113.886 | 13.642 | 11,98 |
| Manhattan | Penn Station/Madison Sq West | 121.862 | 109.149 | 12.713 | 11,65 |
| Manhattan | Midtown East | 119.413 | 116.920 | 2.493 | 2,13 |
| Manhattan | Lincoln Square East | 111.862 | 114.914 | -3.052 | -2,66 |
| Queens | LaGuardia Airport | 104.118 | 108.954 | -4.836 | -4,44 |
| Manhattan | Union Sq | 102.737 | 91.314 | 11.423 | 12,51 |

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, siete crecen (entre +2,1 % en Midtown East y +12,5 % en Union Sq) y tres caen (LaGuardia Airport −4,4 %, Lincoln Square East −2,7 %, JFK Airport −2,2 %). Upper East Side South lidera con 178.609 viajes (+10,1 %). Respecto de abril 2024 entra al top 10 Union Sq y sale Upper West Side South. En los aeropuertos, JFK (puesto 4 del top) cae −2,2 % y LaGuardia (puesto 9 del top) cae −4,4 %: el crecimiento de 2025 es de viajes urbanos, no de aeropuertos. La demanda además se reparte más: el top 10 concentra el 35,6 % de los pickups, frente al 37,5 % de 2024. Fuera de Manhattan, el Bronx casi triplica sus pickups (10.002 → 28.212), aunque sobre una base chica, contra +10,2 % del total.

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
| 2025 | 4 | 5 | 28.320 | 32,73 |
| 2024 | 4 | 5 | 21.677 | 35,11 |

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 32,73 en 2025 y US$ 35,11 en 2024. Es una hora de poco volumen (28.320 viajes, contra 253.620 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 18,0 % de sus viajes toca JFK o LaGuardia (contra 8,3 % en todo el mes) y la distancia media es de 5,75 millas (contra 3,37). En 2025 los viajes de aeropuerto son menos (del 22,1 % al 18,0 % de los viajes de las 5:00), por eso el ingreso por viaje cae un 6,8 %.

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
| ALL ZONES |  | 3.776.409 | 2.792.607 | 73,95 |
| Battery Park | Manhattan | 1.458 | 1.456 | 99,86 |
| SoHo | Manhattan | 32.366 | 32.314 | 99,84 |
| Greenwich Village South | Manhattan | 55.765 | 55.671 | 99,83 |
| West Village | Manhattan | 85.049 | 84.862 | 99,78 |
| Greenwich Village North | Manhattan | 54.991 | 54.868 | 99,78 |

**Interpretación:** El 73,95 % de los viajes de abril 2025 pagó cbd_congestion_fee (2.792.607 de 3.776.409, siempre US$ 0,75). Las cinco zonas con mayor proporción (Battery Park, SoHo, Greenwich Village South, West Village y Greenwich Village North, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En abril 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 50.646 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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
| 2025 | 4 | 0 | Flex Fare | 591.396 | 2,04 | 2,10 |
| 2025 | 4 | 1 | Credit card | 2.635.152 | 25,94 | 22,58 |
| 2025 | 4 | 2 | Cash | 382.522 | 0,00 | 0,00 |
| 2025 | 4 | 3 | No charge | 14.509 | 0,02 | 0,01 |
| 2025 | 4 | 4 | Dispute | 47.550 | 0,05 | 0,04 |
| 2024 | 4 | 0 | Flex Fare | 388.204 | 3,05 | 3,27 |
| 2024 | 4 | 1 | Credit card | 2.535.054 | 25,46 | 22,32 |
| 2024 | 4 | 2 | Cash | 450.227 | 0,00 | 0,00 |
| 2024 | 4 | 3 | No charge | 11.853 | 0,01 | 0,01 |
| 2024 | 4 | 4 | Dispute | 27.617 | 0,05 | 0,08 |

**Interpretación:** Con tarjeta de crédito la propina sube: 25,94 % de la tarifa en 2025 frente a 25,46 % en 2024 (22,6 % y 22,3 % ponderada), y deja propina el 94 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,7 % al 18,4 % de los viajes (388.204 → 591.396 con tarifa > 0) y cuya propina cae del 3,05 % al 2,04 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 12,8 % al 19,4 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,0 % al 69,8 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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
| 2025 | 4 | 314.242 | 55,78 | 175.743 | 141.112 |
| 2024 | 4 | 322.668 | 55,58 | 179.893 | 145.789 |

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia bajan un 2,6 % (322.668 → 314.242) mientras el total de la ciudad sube un 10,2 %, así que su peso cae del 9,4 % al 8,3 % de los viajes. Por aeropuerto, JFK cae −2,3 % y LaGuardia cae −3,2 %. La tarifa promedio se mantiene (US$ 55,58 → US$ 55,78), y la mediana se mantiene en US$ 54,80. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00.

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
| 3.776.409 | 3.427.499 | 348.910 | 10,18 | 18,65 | 19,36 | -3,65 |

**Interpretación:**

- Abril 2025 tuvo 3.776.409 viajes válidos contra 3.427.499 en abril 2024: +348.910 viajes (+10,18 %). La recaudación total (total_amount) crece un 8,3 %, de US$ 96,2 M a US$ 104,2 M.
- Parte del salto es de calendario: abril 2025 tuvo 5 miércoles, y abril 2024, 5 lunes (días flojos). Con el calendario de 2024 la variación sería +9,4 %. Todos los días de la semana crecen (por día), entre +3 % y +15 %, así que el aumento es real.
- La tarifa promedio baja un 3,65 % (de US$ 19,36 a US$ 18,65). La mediana no cambia (US$ 13,50): no bajaron las tarifas, cambió la mezcla de viajes.
- En la mezcla de abril 2025 hay más viajes Flex Fare, que son más baratos (US$ 16,98 contra US$ 19,03 del resto) y pasan del 12 % al 18 % de los viajes, menos viajes a aeropuertos (del 9,4 % al 8,3 %) y menos viajes de más de 10 millas (del 7,8 % al 7,3 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media baja un 2,0 % (de US$ 19,41 a US$ 19,03).
- Calidad: la cuarentena sube del 2,47 % al 4,89 % de las filas leídas (194.144 filas en abril 2025 y 86.790 en abril 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 2,31 % contra 1,31 %) y R04 (total cobrado faltante o negativo: 1,83 % contra 1,24 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en abril 2025 (+10,2 % de viajes, +8,3 % de recaudación). Las zonas que más suman viajes son Upper East Side South (+10,1 %), Midtown Center (+9,7 %) y Times Sq/Theatre District (+12,0 %), mientras los aeropuertos se quedan atrás.
- El peaje de congestión (CBD) alcanza al 73,9 % de los viajes de abril 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Battery Park +9,8 %, SoHo +23,0 % y Greenwich Village South +16,7 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es igual de largo (3,37 contra 3,39 millas) y más barato sin contar las tarifas mayores a US$ 500: la mediana sigue en US$ 13,50, así que el cambio viene de la mezcla de viajes (más Flex Fare, menos aeropuertos y menos viajes largos). La propina con tarjeta sube (25,5 % → 25,9 %).
- Hay 32 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 870,00, en 2025) pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (abril 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 4,89 % y del 2,47 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-04 INGEST_MODE=direct WAREHOUSE=duckdb`.
