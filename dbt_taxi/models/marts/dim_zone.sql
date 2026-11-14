-- Granularidad: 1 fila por LocationID (zona TLC).
-- En ENV=dev el equivalente vive en DuckDB marts.dim_zone (src/modelo.py).
{{ config(materialized='table', tags=['marts']) }}

SELECT
  LocationID::BIGINT AS zone_id,
  Borough AS borough,
  Zone AS zone_name,
  service_zone
FROM {{ source('raw', 'taxi_zone_lookup') }}
