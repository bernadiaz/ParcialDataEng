-- Q5: Viajes y tarifa media que empiezan o terminan en JFK / LaGuardia
-- Params: {{target_year}}, {{target_month}}, {{compare_year}}, {{compare_month}}
WITH air AS (
  SELECT
    CASE
      WHEN pu_zone = 'JFK Airport' OR do_zone = 'JFK Airport' THEN 'JFK'
      WHEN pu_zone = 'LaGuardia Airport' OR do_zone = 'LaGuardia Airport' THEN 'LGA'
    END AS airport,
    source_year,
    source_month,
    fare_amount
  FROM marts.fact_trips
  WHERE (
      (source_year = {{target_year}} AND source_month = {{target_month}})
      OR (source_year = {{compare_year}} AND source_month = {{compare_month}})
    )
    AND (
      pu_zone IN ('JFK Airport', 'LaGuardia Airport')
      OR do_zone IN ('JFK Airport', 'LaGuardia Airport')
    )
)
SELECT
  airport,
  source_year,
  source_month,
  count(*)::BIGINT AS trips,
  round(avg(fare_amount), 4) AS avg_fare
FROM air
WHERE airport IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
