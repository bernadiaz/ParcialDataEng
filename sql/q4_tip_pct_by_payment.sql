-- Q4: Propina promedio (% de tarifa) por payment_type
-- Params: {{target_year}}, {{target_month}}, {{compare_year}}, {{compare_month}}
-- TLC: 1=Credit card, 2=Cash, 3=No charge, 4=Dispute, 0=Voided/Unknown
SELECT
  payment_type,
  CASE payment_type
    WHEN 0 THEN 'Voided/Unknown'
    WHEN 1 THEN 'Credit card'
    WHEN 2 THEN 'Cash'
    WHEN 3 THEN 'No charge'
    WHEN 4 THEN 'Dispute'
    ELSE 'Other'
  END AS payment_label,
  count(*)::BIGINT AS trips,
  round(avg(tip_pct) FILTER (WHERE tip_pct IS NOT NULL), 6) AS avg_tip_pct,
  round(100.0 * avg(tip_pct) FILTER (WHERE tip_pct IS NOT NULL), 4) AS avg_tip_pct_x100
FROM marts.fact_trips
WHERE (source_year = {{target_year}} AND source_month = {{target_month}})
   OR (source_year = {{compare_year}} AND source_month = {{compare_month}})
GROUP BY 1, 2
ORDER BY 1;
