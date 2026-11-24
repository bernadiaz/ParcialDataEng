{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month and payment type. All trips, trips with fare > 0 (the base of the tip %), how many
-- of them tip, and the tip as % of the fare (average per trip and weighted).
select
    year,
    month,
    payment_type,
    count(*) as trips,
    cast(sum(case when fare_amount > 0 then 1 else 0 end) as bigint) as trips_fare_positive,
    cast(sum(case when fare_amount > 0 and tip_amount > 0 then 1 else 0 end) as bigint) as trips_with_tip,
    avg(case when fare_amount > 0 then tip_pct end) as avg_tip_pct,
    100.0 * sum(case when fare_amount > 0 then tip_amount else 0 end)
        / nullif(sum(case when fare_amount > 0 then fare_amount else 0 end), 0) as weighted_tip_pct,
    avg(fare_amount) as avg_fare
from {{ ref('fact_trips') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
group by year, month, payment_type
