{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month and pickup hour. Volume, revenue per trip (with and without the fares above
-- var('fare_cap')), weight of the airports (JFK or LaGuardia at either end), average distance and highest
-- fare. The airports are 2 ids: LEFT JOIN against that small set instead of joining dim_zone twice.
with airports as (

    select location_id from {{ ref('dim_zone') }} where zone in ('JFK Airport', 'LaGuardia Airport')

)

select
    f.year,
    f.month,
    f.pickup_hour,
    count(*) as trips,
    sum(f.total_amount) as revenue,
    sum(f.total_amount) / count(*) as revenue_per_trip,
    cast(sum(case when pa.location_id is not null or da.location_id is not null then 1 else 0 end) as bigint) as airport_trips,
    avg(f.trip_distance) as avg_distance,
    sum(case when f.fare_amount <= {{ var('fare_cap') }} then f.total_amount end)
        / nullif(sum(case when f.fare_amount <= {{ var('fare_cap') }} then 1 else 0 end), 0) as revenue_per_trip_capped,
    max(f.fare_amount) as max_fare
from {{ ref('fact_trips') }} as f
left join airports as pa on pa.location_id = f.pu_location_id
left join airports as da on da.location_id = f.do_location_id
{% if is_incremental() %}
where {{ months_filter('f.year', 'f.month') }}
{% endif %}
group by f.year, f.month, f.pickup_hour
