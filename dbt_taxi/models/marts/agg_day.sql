{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per pickup date. Trips, revenue and CBD toll: trips with the fee > 0 and trips where the
-- column has a value (NULL = the column did not exist in the file of that month).
select
    year,
    month,
    pickup_date,
    count(*) as trips,
    sum(total_amount) as revenue,
    cast(sum(case when cbd_congestion_fee > 0 then 1 else 0 end) as bigint) as trips_with_cbd_fee,
    count(cbd_congestion_fee) as cbd_fee_reported
from {{ ref('fact_trips') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
group by year, month, pickup_date
