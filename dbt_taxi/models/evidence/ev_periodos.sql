-- Grain: two rows per comparison: the month itself (rol = 'mes') and the same month of the previous year
-- (rol = 'anterior'). Used by the evidence that shows one row or one series per period.
select mes, anio, mes_num, mes as periodo, 'mes' as rol, anio as anio_periodo
from {{ ref('ev_comparaciones') }}
union all
select mes, anio, mes_num, mes_anterior as periodo, 'anterior' as rol, anio_anterior as anio_periodo
from {{ ref('ev_comparaciones') }}
