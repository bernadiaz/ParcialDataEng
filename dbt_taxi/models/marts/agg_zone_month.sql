{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month and pickup zone with trips. Incremental by month like agg_zone_hour.
select
    year,
    month,
    pu_location_id,
    count(*) as trips,
    sum(total_amount) as revenue,
    cast(sum(case when cbd_congestion_fee > 0 then 1 else 0 end) as bigint) as trips_with_cbd_fee
from {{ ref('fact_trips') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
group by year, month, pu_location_id
