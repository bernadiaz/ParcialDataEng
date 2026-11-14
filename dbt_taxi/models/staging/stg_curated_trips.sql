-- Vista staging: capa curada ya transformada (derivados + zonas).
{{ config(materialized='view') }}

SELECT *
FROM {{ source('staging', 'curated_trips') }}
