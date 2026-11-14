-- Q3a: % global de viajes con cbd_congestion_fee > 0 (mes asignado)
-- Params: {{target_year}}, {{target_month}}
SELECT
  count(*)::BIGINT AS trips_total,
  count(*) FILTER (WHERE cbd_congestion_fee > 0)::BIGINT AS trips_cbd,
  round(
    100.0 * count(*) FILTER (WHERE cbd_congestion_fee > 0) / nullif(count(*), 0),
    4
  ) AS pct_cbd
FROM marts.fact_trips
WHERE source_year = {{target_year}} AND source_month = {{target_month}};
