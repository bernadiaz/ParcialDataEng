-- Reconciliation inside the warehouse: for every month, fact_trips must hold exactly the rows of
-- RAW.YELLOW_TRIPS (nothing lost or duplicated by the joins). Returns the months that differ.
-- It reads RAW and fact_trips, so meta.dagster.ref attaches it to fact_trips (a Dagster asset check).
{{ config(meta={'dagster': {'ref': {'name': 'fact_trips'}}}) }}
with raw_counts as (
    select year, month, count(*) as raw_rows
    from {{ source('raw', 'yellow_trips') }}
    group by year, month
),

fact_counts as (
    select year, month, count(*) as fact_rows
    from {{ ref('fact_trips') }}
    group by year, month
)

select r.year, r.month, r.raw_rows, f.fact_rows
from raw_counts as r
full outer join fact_counts as f on r.year = f.year and r.month = f.month
where coalesce(r.raw_rows, -1) <> coalesce(f.fact_rows, -1)
