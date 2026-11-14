-- Granularidad: zona de origen × fecha × hora.
{{ config(materialized='table', tags=['marts', 'finops']) }}

SELECT
  pu_zone_id,
  date_id,
  pickup_hour,
  count(*) AS trips,
  sum(total_amount) AS total_revenue,
  avg(duration_min) AS avg_duration_min
FROM {{ ref('fact_trips') }}
GROUP BY 1, 2, 3
