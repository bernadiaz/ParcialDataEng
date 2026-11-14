-- Q3b: Top 5 zonas de origen con mayor proporción de viajes con CBD fee > 0
-- Params: {{target_year}}, {{target_month}}
-- Mínimo 1000 viajes para evitar ruido de zonas chicas.
SELECT
  pu_zone_id,
  pu_zone,
  count(*)::BIGINT AS trips,
  count(*) FILTER (WHERE cbd_congestion_fee > 0)::BIGINT AS trips_cbd,
  round(
    100.0 * count(*) FILTER (WHERE cbd_congestion_fee > 0) / nullif(count(*), 0),
    4
  ) AS pct_cbd
FROM marts.fact_trips
WHERE source_year = {{target_year}} AND source_month = {{target_month}}
GROUP BY 1, 2
HAVING count(*) >= 1000
ORDER BY pct_cbd DESC
LIMIT 5;
