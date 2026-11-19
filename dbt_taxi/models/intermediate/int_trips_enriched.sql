-- Intermediate (ephemeral). Part 4: derived columns and enrichment with the zone lookup.
with trips as (

    select * from {{ ref('stg_yellow_trips') }}

),

zones as (

    select location_id, borough, zone from {{ ref('stg_taxi_zones') }}

),

timed as (

    select
        trips.*,
        {{ dbt.datediff('trips.pickup_datetime', 'trips.dropoff_datetime', 'second') }} as duration_seconds
    from trips

)

select
    {{ dbt.hash("concat(t.source_file, '#', cast(t.source_row_number as varchar))") }} as trip_key,
    t.vendor_id,
    t.pickup_datetime,
    t.dropoff_datetime,
    cast(t.pickup_datetime as date) as pickup_date,
    extract(hour from t.pickup_datetime) as pickup_hour,
    {{ dow_iso('t.pickup_datetime') }} as pickup_dow,
    t.passenger_count,
    t.trip_distance,
    round(t.duration_seconds / 60.0, 2) as duration_min,
    case when t.duration_seconds > 0
        then round(t.trip_distance / (t.duration_seconds / 3600.0), 2)
    end as avg_speed_mph,
    t.ratecode_id,
    t.store_and_fwd_flag,
    t.payment_type,
    t.pu_location_id,
    pu.borough as pu_borough,
    pu.zone as pu_zone,
    t.do_location_id,
    dz.borough as do_borough,
    dz.zone as do_zone,
    t.fare_amount,
    t.extra,
    t.mta_tax,
    t.tip_amount,
    t.tolls_amount,
    t.improvement_surcharge,
    t.congestion_surcharge,
    t.airport_fee,
    t.cbd_congestion_fee,
    t.total_amount,
    case when t.fare_amount > 0 then round(100.0 * t.tip_amount / t.fare_amount, 2) end as tip_pct,
    t.quality_flags,
    t.source_file,
    t.source_row_number,
    t.year,
    t.month
from timed as t
left join zones as pu on t.pu_location_id = pu.location_id
left join zones as dz on t.do_location_id = dz.location_id
