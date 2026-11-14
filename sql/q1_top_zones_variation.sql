-- Q1: Top 10 zonas de origen por viajes (mes asignado) y variación vs mismo mes año anterior
-- Params: {{target_year}}, {{target_month}}, {{compare_year}}, {{compare_month}}
WITH cur AS (
  SELECT pu_zone_id, pu_zone, count(*)::BIGINT AS trips
  FROM marts.fact_trips
  WHERE source_year = {{target_year}} AND source_month = {{target_month}}
  GROUP BY 1, 2
),
prev AS (
  SELECT pu_zone_id, count(*)::BIGINT AS trips
  FROM marts.fact_trips
  WHERE source_year = {{compare_year}} AND source_month = {{compare_month}}
  GROUP BY 1
)
SELECT
  c.pu_zone_id,
  c.pu_zone,
  c.trips AS trips_target,
  COALESCE(p.trips, 0) AS trips_compare,
  c.trips - COALESCE(p.trips, 0) AS delta_trips,
  CASE
    WHEN COALESCE(p.trips, 0) = 0 THEN NULL
    ELSE round(100.0 * (c.trips - p.trips) / p.trips, 2)
  END AS pct_change
FROM cur c
LEFT JOIN prev p ON c.pu_zone_id = p.pu_zone_id
ORDER BY c.trips DESC
LIMIT 10;
