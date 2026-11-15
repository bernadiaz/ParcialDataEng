{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per pickup zone, pickup date and pickup hour (only combinations with trips).
-- total_revenue = sum(total_amount). Incremental by (year, month) like fact_trips (delete month + append).
select
    pu_location_id,
    pickup_date,
    pickup_hour,
    year,
    month,
    count(*) as trips,
    round(sum(total_amount), 2) as total_revenue,
    round(avg(duration_min), 2) as avg_duration_min
from {{ ref('fact_trips') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
group by pu_location_id, pickup_date, pickup_hour, year, month
