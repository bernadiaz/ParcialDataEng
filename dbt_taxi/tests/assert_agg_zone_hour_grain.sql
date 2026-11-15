-- agg_zone_hour must have one row per (zone, date, hour) and add up to fact_trips per month.
with duplicated as (
    select pu_location_id, pickup_date, pickup_hour
    from {{ ref('agg_zone_hour') }}
    group by pu_location_id, pickup_date, pickup_hour
    having count(*) > 1
),

totals as (
    select a.year, a.month, a.agg_trips, f.fact_trips
    from (select year, month, sum(trips) as agg_trips from {{ ref('agg_zone_hour') }} group by year, month) as a
    full outer join (select year, month, count(*) as fact_trips from {{ ref('fact_trips') }} group by year, month) as f
        on a.year = f.year and a.month = f.month
    where coalesce(a.agg_trips, -1) <> coalesce(f.fact_trips, -1)
)

select 'duplicated grain' as problem, cast(pu_location_id as varchar) as detail from duplicated
union all
select 'trips do not add up' as problem, concat(cast(year as varchar), '-', cast(month as varchar)) as detail from totals
