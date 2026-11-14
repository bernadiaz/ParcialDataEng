-- Granularidad: 1 fila por fecha de pickup presente en los hechos.
{{ config(materialized='table', tags=['marts']) }}

SELECT DISTINCT
  pickup_date AS date_id,
  year(pickup_date) AS year,
  month(pickup_date) AS month,
  day(pickup_date) AS day,
  dayofweek(pickup_date) AS dow
FROM {{ ref('stg_curated_trips') }}
WHERE pickup_date IS NOT NULL
