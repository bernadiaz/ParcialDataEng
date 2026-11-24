{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month. Trips that start or end at JFK or LaGuardia (a trip between both counts once):
-- totals per airport, average and median fare, average without the fares above var('fare_cap'), highest fare
-- and the median of the JFK flat fare (RatecodeID 2).
with airports as (

    select location_id, zone from {{ ref('dim_zone') }} where zone in ('JFK Airport', 'LaGuardia Airport')

),

trips as (

    select f.year, f.month, f.fare_amount, f.ratecode_id, pa.zone as pu_airport, da.zone as do_airport
    from {{ ref('fact_trips') }} as f
    left join airports as pa on pa.location_id = f.pu_location_id
    left join airports as da on da.location_id = f.do_location_id
    where (pa.location_id is not null or da.location_id is not null)
    {% if is_incremental() %}
      and {{ months_filter('f.year', 'f.month') }}
    {% endif %}

)

select
    year,
    month,
    count(*) as airport_trips,
    cast(sum(case when pu_airport = 'JFK Airport' or do_airport = 'JFK Airport' then 1 else 0 end) as bigint) as jfk_trips,
    cast(sum(case when pu_airport = 'LaGuardia Airport' or do_airport = 'LaGuardia Airport' then 1 else 0 end) as bigint) as lga_trips,
    cast(sum(case when pu_airport is not null then 1 else 0 end) as bigint) as pickups_at_airport,
    avg(fare_amount) as avg_fare,
    median(fare_amount) as median_fare,
    avg(case when fare_amount <= {{ var('fare_cap') }} then fare_amount end) as avg_fare_capped,
    max(fare_amount) as max_fare,
    median(case when ratecode_id = 2 then fare_amount end) as jfk_flat_fare
from trips
group by year, month
