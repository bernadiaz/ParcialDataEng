-- Evidence of the Spanish reports (results/YYYY/RESULTS_MM.md) and of the Superset evidence dashboards.
-- Grain: one row per comparison = a month (mes) whose same month of the previous year (mes_anterior) is also
-- loaded. Every other ev_* model starts here, so a month without its comparison month has no evidence, and the
-- report of that month says so instead of inventing a figure.
select
    {{ mes_label('a.year', 'a.month') }} as mes,
    a.year as anio,
    a.month as mes_num,
    {{ mes_label('b.year', 'b.month') }} as mes_anterior,
    b.year as anio_anterior
from {{ ref('agg_month_profile') }} as a
inner join {{ ref('agg_month_profile') }} as b on b.year = a.year - 1 and b.month = a.month
