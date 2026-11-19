# Resultados: junio 2025 vs junio 2024

> En junio 2025 los taxis amarillos hicieron 4.050.910 viajes válidos, +17,7 % que en junio 2024 (3.440.443), con una recaudación de US$ 115,1 M (+17,1 %).

| | |
|---|---|
| Comando | `make all MES=2025-06 INGEST_MODE=direct WAREHOUSE=duckdb` |
| Modo | local, sin nube: los archivos se descargan de la TLC, la calidad corre en DuckDB y el warehouse es un archivo DuckDB |
| Consultas | marts de dbt en DuckDB |
| Archivos de la TLC | `yellow_tripdata_2025-06.parquet` y `yellow_tripdata_2024-06.parquet` |
| Corrida | `20261118T045111Z-8bd5af`, 2026-11-18 04:51 UTC |

Las interpretaciones no son texto fijo: `src/interpretacion.py` las redacta en cada corrida a partir de los resultados de las consultas, de las consultas de contexto (`sql/contexto/`) y de los reportes de esquema y de calidad de cada archivo. Los montos están en dólares; las tarifas mayores a US$ 500 se señalan como atípicas porque ninguna regla de calidad les pone un tope.

## Calidad de los datos y cuarentena

Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema (`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year=2025/month=06/` y el mismo camino para 2024, la tabla `raw.yellow_quarantine`). Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen (`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes `leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.

| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2025-06 | `yellow_tripdata_2025-06.parquet` | 4.322.960 | 4.322.960 | 4.050.910 | 272.050 | 6,29 % | 1.143.555 (26,45 %) | sí |
| 2024-06 | `yellow_tripdata_2024-06.parquet` | 3.539.193 | 3.539.193 | 3.440.443 | 98.750 | 2,79 % | 437.566 (12,36 %) | sí |

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

- La cuarentena sube del 2,79 % al 6,29 % de las filas leídas (272.050 filas en junio 2025 y 98.750 en junio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,13 % contra 1,50 %) y R04 (total cobrado faltante o negativo: 1,72 % contra 1,38 %).
- Las reglas de advertencia no sacan filas: 1.143.555 filas aceptadas de junio 2025 (26,5 %) llevan alguna marca, la más común R05 (cantidad de pasajeros NULL o 0: 28,6 %, contra 12,6 % en junio 2024).
- En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

- Esquema de junio 2025: el archivo coincide con el contrato (mismas columnas y tipos).
- Esquema de junio 2024: el archivo no trae `cbd_congestion_fee` (el peaje de congestión todavía no existía): queda en NULL, no en 0, para no confundir "no se cobró" con "no existía".

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

**Interpretación:** Ocho de las diez zonas con más pickups están en Manhattan. Dentro del top 10, nueve crecen (entre +3,7 % en Midtown East y +12,2 % en Penn Station/Madison Sq West) y una cae (LaGuardia Airport −3,5 %). JFK Airport lidera con 170.532 viajes (+12,2 %) y desplaza a Midtown Center, que encabezaba junio 2024. En los aeropuertos, JFK (puesto 1 del top) crece +12,2 % y LaGuardia (puesto 9 del top) cae −3,5 %: los dos quedan por debajo del total de la ciudad (+17,7 %). La demanda además se reparte más: el top 10 concentra el 33,3 % de los pickups, frente al 36,9 % de 2024. Fuera de Manhattan, el Bronx más que triplica sus pickups (10.331 → 33.860), aunque sobre una base chica, contra +17,7 % del total.

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

**Interpretación:** La hora con mayor ingreso promedio por viaje es las 5:00 en los dos años: US$ 32,56 en 2025 y US$ 37,77 en 2024. Es una hora de poco volumen (33.295 viajes, contra 263.870 a las 18:00, la hora pico de demanda en ambos años). Gana porque a esa hora pesan los viajes largos: el 16,1 % de sus viajes toca JFK o LaGuardia (contra 8,6 % en todo el mes) y la distancia media es de 5,78 millas (contra 3,61). En 2025 los viajes de aeropuerto son menos (del 24,8 % al 16,1 % de los viajes de las 5:00) y la distancia media baja (de 6,16 a 5,78 millas), por eso el ingreso por viaje cae un 13,8 %. Ojo con el tercer puesto de 2025 (las 14:00, US$ 30,80): es artificial, porque lo infla un viaje con una tarifa de US$ 325.478,05. Sin las tarifas mayores a US$ 500, esa hora queda en US$ 29,40.

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

**Interpretación:** El 73,75 % de los viajes de junio 2025 pagó cbd_congestion_fee (2.987.370 de 4.050.910, siempre US$ 0,75). Las cinco zonas con mayor proporción (Greenwich Village South, West Village, SoHo, Greenwich Village North y Union Sq, alrededor del 100 %) están todas en Manhattan, dentro de la zona de peaje. En junio 2024 la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene contra qué compararse. La regla R10 marcó 49.930 filas con un cobro anómalo (negativo, es decir una reversión, o anterior al inicio del peaje): se conservan con su marca.

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

**Interpretación:** Con tarjeta de crédito la propina sube: 25,25 % de la tarifa en 2025 frente a 24,70 % en 2024 (22,1 % y 22,0 % ponderada), y deja propina el 93 % de esos viajes. En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen. El cambio grande es Flex Fare (payment_type 0, tarifa fija acordada por app), que pasa del 11,6 % al 27,6 % de los viajes (387.216 → 936.118 con tarifa > 0) y cuya propina cae del 3,02 % al 1,49 %. Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 suben del 12,6 % al 28,6 % de las filas leídas. La tarjeta pierde peso entre las formas de pago: del 74,0 % al 62,1 % de los viajes. "No charge" y "Dispute" tienen una propina cercana a 0, como es esperable.

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

**Interpretación:** Los viajes que empiezan o terminan en JFK o LaGuardia suben un 3,5 % (334.782 → 346.603) mientras el total de la ciudad sube un 17,7 %, así que su peso cae del 9,7 % al 8,6 % de los viajes. Por aeropuerto, JFK crece +9,2 % y LaGuardia cae −3,5 %. La tarifa promedio sube de US$ 56,24 a US$ 57,75 (+2,7 %), pero esa suba está exagerada: la produce un solo viaje de 2025 con fare_amount = US$ 325.478,05 (de Midtown Center a JFK Airport, 20,6 millas, pago efectivo). Excluyendo las tarifas mayores a US$ 500 en los dos años, el promedio pasa de US$ 56,22 a US$ 56,78 (+1,0 %), y la mediana sube de US$ 55,50 a US$ 56,90. La tarifa fija de JFK (RatecodeID 2) sigue en US$ 70,00. Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.

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

**Interpretación:**

- Junio 2025 tuvo 4.050.910 viajes válidos contra 3.440.443 en junio 2024: +610.467 viajes (+17,74 %). La recaudación total (total_amount) crece un 17,1 %, de US$ 98,3 M a US$ 115,1 M.
- El calendario juega en contra de junio 2025: junio 2025 tuvo 5 lunes (días flojos), y junio 2024, 5 sábados (días fuertes). Con el calendario de 2024 la variación sería +18,6 %. Todos los días de la semana crecen (por día), entre +11 % y +27 %, así que el aumento es real.
- La tarifa promedio baja un 0,79 % (de US$ 19,86 a US$ 19,70); sin las tarifas mayores a US$ 500 (entre ellas, el viaje de US$ 325.478) la baja es del 1,2 % (de US$ 19,86 a US$ 19,62). La mediana pasa de US$ 14,20 a US$ 14,65 (+3,2 %).
- En la mezcla de junio 2025 hay más viajes Flex Fare, que son más baratos (US$ 18,51 contra US$ 20,04 del resto) y pasan del 12 % al 28 % de los viajes y menos viajes a aeropuertos (del 9,7 % al 8,6 %). Sin Flex Fare y sin tarifas mayores a US$ 500, la tarifa media casi no cambia (de US$ 19,77 a US$ 20,04). El viaje promedio es más largo: 3,61 contra 3,42 millas.
- Calidad: la cuarentena sube del 2,79 % al 6,29 % de las filas leídas (272.050 filas en junio 2025 y 98.750 en junio 2024). La explican sobre todo R03 (distancia faltante, cero o negativa, o mayor al máximo fijado: 3,13 % contra 1,50 %) y R04 (total cobrado faltante o negativo: 1,72 % contra 1,38 %). En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena.

## Conclusiones

- La demanda de taxis amarillos crece con fuerza en junio 2025 (+17,7 % de viajes, +17,1 % de recaudación). Las zonas que más suman viajes son East Village (+28,0 %), JFK Airport (+12,2 %) y Upper East Side South (+8,5 %), mientras los aeropuertos quedan por debajo del total.
- El peaje de congestión (CBD) alcanza al 73,7 % de los viajes de junio 2025. Las zonas con mayor proporción de cobro también crecen en viajes (Greenwich Village South +12,1 %, West Village +7,3 % y SoHo +13,8 %): en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.
- El viaje promedio es más largo (3,61 contra 3,42 millas) y más barato sin contar las tarifas mayores a US$ 500 (mediana US$ 14,20 → US$ 14,65). La propina con tarjeta sube (24,7 % → 25,3 %).
- Los promedios son frágiles: 51 viajes con tarifas mayores a US$ 500 (el mayor, de US$ 325.478,05, en 2025) alcanzan para mover el ranking de horas, la tarifa media de los aeropuertos y la tarifa media del mes, por eso se reportan también la mediana y el promedio sin tarifas mayores a US$ 500. La siguiente regla de calidad a agregar es un tope de tarifa o de tarifa por milla.
- Los archivos traen cambios de formato que el pipeline absorbe sin romperse (junio 2024: no trae cbd_congestion_fee, que queda en NULL). La cuarentena es del 6,29 % y del 2,79 % de las filas leídas y los dos meses reconcilian. Las cifras salen de los marts de dbt en DuckDB (modo local) y se reproducen con `make all MES=2025-06 INGEST_MODE=direct WAREHOUSE=duckdb`.
