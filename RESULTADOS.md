# RESULTADOS — preguntas de negocio

Mes asignado: **2025-03**. Comparación: **2024-03**.

> Generado con `make questions-host MES=2025-03` sobre `marts.*` en `data/warehouse/nyc_taxi.duckdb`.

## 1. Top 10 zonas de origen y variación vs 2024

Consulta: `sql/q1_top_zones_variation.sql`

| pu_zone_id | pu_zone | trips_target | trips_compare | delta_trips | pct_change |
| --- | --- | --- | --- | --- | --- |
| 161 | Midtown Center | 175003 | 158934 | 16069 | 10.11 |
| 237 | Upper East Side South | 165048 | 152185 | 12863 | 8.45 |
| 132 | JFK Airport | 148190 | 149443 | -1253 | -0.84 |
| 236 | Upper East Side North | 147778 | 142672 | 5106 | 3.58 |
| 230 | Times Sq/Theatre District | 130654 | 118502 | 12152 | 10.25 |
| 186 | Penn Station/Madison Sq West | 127828 | 111748 | 16080 | 14.39 |
| 162 | Midtown East | 123927 | 120623 | 3304 | 2.74 |
| 142 | Lincoln Square East | 113220 | 111801 | 1419 | 1.27 |
| 234 | Union Sq | 110010 | 94576 | 15434 | 16.32 |
| 79 | East Village | 106594 | 89442 | 17152 | 19.18 |

Interpretación: Las zonas con más orígenes en 2025-03 concentran la demanda Manhattan/aeropuertos; la variación vs 2024-03 muestra dónde creció o cayó el tráfico yellow.

## 2. Hora con mayor ingreso promedio por viaje

Consulta: `sql/q2_peak_hour_avg_revenue.sql`

| pickup_hour | trips | avg_revenue_per_trip |
| --- | --- | --- |
| 5 | 53435 | 34.3791 |

Interpretación: La hora pico de ingreso promedio suele alinearse con traslados largos (aeropuerto/madrugada) más que con el horario de máximo volumen.

## 3. CBD congestion fee (> 0) y top 5 zonas

Consulta: `sql/q3_cbd_fee_share.sql` + `sql/q3b_cbd_top_zones.sql`

### Global (mes asignado)

| trips_total | trips_cbd | pct_cbd |
| --- | --- | --- |
| 3954755 | 2936152 | 74.2436 |

### Top 5 zonas de origen (mín. 1000 viajes)

| pu_zone_id | pu_zone | trips | trips_cbd | pct_cbd |
| --- | --- | --- | --- | --- |
| 211 | SoHo | 34497 | 34438 | 99.829 |
| 113 | Greenwich Village North | 58167 | 58025 | 99.7559 |
| 249 | West Village | 95986 | 95749 | 99.7531 |
| 144 | Little Italy/NoLiTa | 45848 | 45733 | 99.7492 |
| 114 | Greenwich Village South | 64035 | 63874 | 99.7486 |

Interpretación: El CBD congestion fee aplica en 2025-03 (archivo 2025+). Las zonas con mayor proporción concentran pickups dentro/hacia el distrito de congestion pricing.

## 4. Propina promedio (% tarifa) por tipo de pago

Consulta: `sql/q4_tip_pct_by_payment.sql`

| payment_type | payment_label | trips | avg_tip_pct | avg_tip_pct_x100 |
| --- | --- | --- | --- | --- |
| 0 | Voided/Unknown | 1234067 | 0.024472 | 2.4472 |
| 1 | Credit card | 5237503 | 0.256612 | 25.6612 |
| 2 | Cash | 835179 | 1.5e-05 | 0.0015 |
| 3 | No charge | 27239 | 0.000107 | 0.0107 |
| 4 | Dispute | 73574 | 0.001079 | 0.1079 |

Interpretación: Credit card (1) registra propina en el datáfono; **Cash (2) no es interpretable**: la propina en efectivo casi nunca entra en `tip_amount`, por eso el % queda sesgado hacia 0. No charge/Dispute tampoco reflejan propina real.

## 5. Viajes y tarifa media JFK / LaGuardia

Consulta: `sql/q5_airport_trips.sql`

| airport | source_year | source_month | trips | avg_fare |
| --- | --- | --- | --- | --- |
| JFK | 2024 | 3 | 179236 | 65.1214 |
| JFK | 2025 | 3 | 177529 | 64.4487 |
| LGA | 2024 | 3 | 140976 | 43.701 |
| LGA | 2025 | 3 | 140676 | 43.7335 |

Interpretación: JFK y LaGuardia concentran viajes de mayor tarifa media que el promedio urbano por distancia y airport fee.

## 6. Variación entre los dos meses

Consulta: `sql/q6_month_variation.sql`

| trips_target | trips_compare | delta_trips | pct_trips | avg_fare_target | avg_fare_compare | delta_fare | pct_fare |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3954755 | 3452807 | 501948 | 14.54 | 18.3996 | 19.0626 | -0.6631 | -3.48 |

Hipótesis de causa (≤ 5 líneas):

Entre 2024-03 y 2025-03 cambia el volumen y/o la tarifa media. Hipótesis: (1) recuperación/estacionalidad de demanda yellow; (2) efecto del CBD congestion fee y surcharges en 2025; (3) cambios de oferta (Uber/Lyft) que desplazan viajes cortos; (4) inflación de tarifas TLC; (5) calidad de datos/filtrado de cuarentena distinto entre años.
