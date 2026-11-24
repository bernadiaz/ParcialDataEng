{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per month and rank (1..3): the trips with the highest fare among those above
-- var('fare_cap'). It filters before numbering, so only a handful of rows are ranked.
with ranked as (

    select
        year,
        month,
        fare_amount,
        total_amount,
        trip_distance,
        payment_type,
        pickup_hour,
        pu_location_id,
        do_location_id,
        row_number() over (partition by year, month order by fare_amount desc, trip_key) as rank_in_month
    from {{ ref('fact_trips') }}
    where fare_amount > {{ var('fare_cap') }}
    {% if is_incremental() %}
      and {{ months_filter() }}
    {% endif %}

)

select *
from ranked
where rank_in_month <= 3
