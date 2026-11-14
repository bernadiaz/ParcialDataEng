-- Q2: Hora del día con mayor ingreso promedio por viaje (ambos meses del modelo)
-- Params: {{target_year}}, {{target_month}}, {{compare_year}}, {{compare_month}}
SELECT
  pickup_hour,
  count(*)::BIGINT AS trips,
  round(avg(total_amount), 4) AS avg_revenue_per_trip
FROM marts.fact_trips
WHERE (source_year = {{target_year}} AND source_month = {{target_month}})
   OR (source_year = {{compare_year}} AND source_month = {{compare_month}})
GROUP BY 1
ORDER BY avg_revenue_per_trip DESC
LIMIT 1;
