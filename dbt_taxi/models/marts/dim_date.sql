-- Grain: one row per calendar day of every processed month (plan 5.6: calendar of processed months).
with processed as (

    select distinct year, month from {{ ref('stg_yellow_trips') }}

),

day_offsets as (

    -- 0..30 without a generator function (portable): the zone lookup always has more than 31 rows.
    select row_number() over (order by location_id) - 1 as day_offset
    from {{ ref('stg_taxi_zones') }}

),

days as (

    select
        p.year,
        p.month,
        cast({{ dbt.dateadd('day', 'o.day_offset', month_start('p.year', 'p.month')) }} as date) as date_day
    from processed as p
    cross join day_offsets as o
    where o.day_offset < 31

)

select
    date_day as date_key,
    year,
    month,
    extract(day from date_day) as day_of_month,
    {{ dow_iso('date_day') }} as day_of_week_iso,
    {{ day_name(dow_iso('date_day')) }} as day_name,
    {{ dow_iso('date_day') }} in (6, 7) as is_weekend,
    concat(cast(year as varchar), '-', lpad(cast(month as varchar), 2, '0')) as year_month
from days
where extract(month from date_day) = month
