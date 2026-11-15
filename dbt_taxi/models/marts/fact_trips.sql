{{
    config(
        materialized='incremental',
        incremental_strategy='append',
        on_schema_change='append_new_columns',
        pre_hook="{% if is_incremental() %}delete from {{ this }} where {{ months_filter() }}{% endif %}"
    )
}}
-- Grain: one row per accepted trip. Incremental by (year, month): the pre-hook deletes the processed
-- months and the run appends them again, so reprocessing a month replaces only that month.
-- Not delete+insert with unique_key=(year, month): that key is not unique, so the DELETE ... USING
-- join would compare millions x millions of rows.
-- Zone names live in dim_zone; the fact keeps keys and measures.
select
    trip_key,
    pickup_date,
    pu_location_id,
    do_location_id,
    vendor_id,
    ratecode_id,
    payment_type,
    store_and_fwd_flag,
    pickup_datetime,
    dropoff_datetime,
    pickup_hour,
    pickup_dow,
    passenger_count,
    trip_distance,
    duration_min,
    avg_speed_mph,
    fare_amount,
    extra,
    mta_tax,
    tip_amount,
    tolls_amount,
    improvement_surcharge,
    congestion_surcharge,
    airport_fee,
    cbd_congestion_fee,
    total_amount,
    tip_pct,
    quality_flags,
    source_file,
    source_row_number,
    year,
    month
from {{ ref('int_trips_enriched') }}
{% if is_incremental() %}
where {{ months_filter() }}
{% endif %}
