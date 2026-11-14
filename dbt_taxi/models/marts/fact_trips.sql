-- Granularidad: 1 fila por viaje curado (aceptado por calidad).
-- Incremental por mes en Snowflake (FinOps); en dev: rebuild DuckDB.
{{ config(
    materialized='incremental',
    unique_key=['source_year', 'source_month', 'trip_sk'],
    tags=['marts', 'finops']
) }}

SELECT *
FROM {{ ref('stg_curated_trips') }}

{% if is_incremental() %}
WHERE source_year = {{ var('mes').split('-')[0] | int }}
  AND source_month = {{ var('mes').split('-')[1] | int }}
{% endif %}
