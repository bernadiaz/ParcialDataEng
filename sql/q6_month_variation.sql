-- Q6: Variación de viajes totales y tarifa media entre los dos meses
-- Params: {{target_year}}, {{target_month}}, {{compare_year}}, {{compare_month}}
WITH m AS (
  SELECT
    source_year,
    source_month,
    count(*)::BIGINT AS trips,
    avg(fare_amount) AS avg_fare
  FROM marts.fact_trips
  WHERE (source_year = {{target_year}} AND source_month = {{target_month}})
     OR (source_year = {{compare_year}} AND source_month = {{compare_month}})
  GROUP BY 1, 2
),
piv AS (
  SELECT
    max(trips) FILTER (WHERE source_year = {{target_year}}) AS trips_target,
    max(trips) FILTER (WHERE source_year = {{compare_year}}) AS trips_compare,
    max(avg_fare) FILTER (WHERE source_year = {{target_year}}) AS fare_target,
    max(avg_fare) FILTER (WHERE source_year = {{compare_year}}) AS fare_compare
  FROM m
)
SELECT
  trips_target,
  trips_compare,
  trips_target - trips_compare AS delta_trips,
  round(100.0 * (trips_target - trips_compare) / nullif(trips_compare, 0), 2) AS pct_trips,
  round(fare_target, 4) AS avg_fare_target,
  round(fare_compare, 4) AS avg_fare_compare,
  round(fare_target - fare_compare, 4) AS delta_fare,
  round(100.0 * (fare_target - fare_compare) / nullif(fare_compare, 0), 2) AS pct_fare
FROM piv;
