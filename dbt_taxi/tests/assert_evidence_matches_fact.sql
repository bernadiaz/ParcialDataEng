-- Every monthly aggregate behind the evidence must add up to fact_trips, month by month: the reports and Superset
-- read the aggregates, so a month that does not add up would show figures that the trips do not back.
-- It reads several models, so meta.dagster.ref attaches it to agg_month_profile (a Dagster asset check).
{{ config(meta={'dagster': {'ref': {'name': 'agg_month_profile'}}}) }}
with fact as (
    select year, month, count(*) as trips from {{ ref('fact_trips') }} group by year, month
),

aggregates as (
    select 'agg_month_profile' as model, year, month, sum(trips) as trips from {{ ref('agg_month_profile') }} group by year, month
    union all
    select 'agg_zone_month' as model, year, month, sum(trips) as trips from {{ ref('agg_zone_month') }} group by year, month
    union all
    select 'agg_hour_month' as model, year, month, sum(trips) as trips from {{ ref('agg_hour_month') }} group by year, month
    union all
    select 'agg_day' as model, year, month, sum(trips) as trips from {{ ref('agg_day') }} group by year, month
    union all
    select 'agg_payment_month' as model, year, month, sum(trips) as trips from {{ ref('agg_payment_month') }} group by year, month
),

models as (
    select distinct model from aggregates
)

select m.model, f.year, f.month, f.trips as fact_trips, a.trips as aggregate_trips
from fact as f
cross join models as m
left join aggregates as a on a.model = m.model and a.year = f.year and a.month = f.month
where coalesce(a.trips, -1) <> f.trips
