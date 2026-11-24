{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month (year, month). Volume, revenue, fares, distance, payment mix and CBD toll of the
-- accepted trips. Incremental by month like agg_zone_hour. Medians and averages are computed here once, so
-- the Spanish reports and Superset read the same stored values.
-- var('fare_cap'): cap of the averages "without outliers" (no quality rule limits the fare).
select
    year,
    month,
    count(*) as trips,
    sum(total_amount) as revenue,
    avg(fare_amount) as avg_fare,
    median(fare_amount) as median_fare,
    avg(case when fare_amount <= {{ var('fare_cap') }} then fare_amount end) as avg_fare_capped,
    cast(sum(case when fare_amount > {{ var('fare_cap') }} then 1 else 0 end) as bigint) as fares_over_cap,
    max(fare_amount) as max_fare,
    avg(trip_distance) as avg_distance,
    100.0 * sum(case when trip_distance > {{ var('long_trip_miles') }} then 1 else 0 end) / count(*) as pct_long_trips,
    avg(duration_min) as avg_duration_min,
    cast(sum(case when payment_type = 0 then 1 else 0 end) as bigint) as flex_trips,
    avg(case when payment_type = 0 then fare_amount end) as avg_fare_flex,
    avg(case when payment_type <> 0 then fare_amount end) as avg_fare_not_flex,
    avg(case when payment_type = 0 and fare_amount <= {{ var('fare_cap') }} then fare_amount end) as avg_fare_flex_capped,
    avg(case when payment_type <> 0 and fare_amount <= {{ var('fare_cap') }} then fare_amount end) as avg_fare_not_flex_capped,
    cast(sum(case when payment_type = 1 then 1 else 0 end) as bigint) as card_trips,
    cast(sum(case when payment_type = 2 then 1 else 0 end) as bigint) as cash_trips,
    count(distinct pickup_date) as days_with_trips,
    count(cbd_congestion_fee) as cbd_fee_reported,
    cast(sum(case when cbd_congestion_fee > 0 then 1 else 0 end) as bigint) as trips_with_cbd_fee,
    avg(case when cbd_congestion_fee > 0 then cbd_congestion_fee end) as avg_cbd_fee,
    min(case when cbd_congestion_fee > 0 then cbd_congestion_fee end) as min_cbd_fee,
    max(cbd_congestion_fee) as max_cbd_fee
from {{ ref('fact_trips') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
group by year, month
