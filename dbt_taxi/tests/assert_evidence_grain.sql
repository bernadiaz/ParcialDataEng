-- Grain of the evidence tables: one row per comparison and key. A duplicated row would show a figure twice on a
-- dashboard (or double it in a chart). It reads several models, so meta.dagster.ref attaches it to ev_indicadores.
{{ config(meta={'dagster': {'ref': {'name': 'ev_indicadores'}}}) }}
select 'ev_indicadores' as model, concat(mes, ' ', indicador_id) as key, count(*) as n
from {{ ref('ev_indicadores') }} group by mes, indicador_id having count(*) > 1
union all
select 'ev_zonas' as model, concat(mes, ' ', cast(pu_location_id as varchar)) as key, count(*) as n
from {{ ref('ev_zonas') }} group by mes, pu_location_id having count(*) > 1
union all
select 'ev_boroughs' as model, concat(mes, ' ', borough) as key, count(*) as n
from {{ ref('ev_boroughs') }} group by mes, borough having count(*) > 1
union all
select 'ev_horas' as model, concat(mes, ' ', cast(hora as varchar)) as key, count(*) as n
from {{ ref('ev_horas') }} group by mes, hora having count(*) > 1
union all
select 'ev_dias' as model, concat(mes, ' ', periodo, ' ', cast(dia as varchar)) as key, count(*) as n
from {{ ref('ev_dias') }} group by mes, periodo, dia having count(*) > 1
union all
select 'ev_dias_semana' as model, concat(mes, ' ', cast(dia_iso as varchar)) as key, count(*) as n
from {{ ref('ev_dias_semana') }} group by mes, dia_iso having count(*) > 1
union all
select 'ev_pagos' as model, concat(mes, ' ', forma_pago) as key, count(*) as n
from {{ ref('ev_pagos') }} group by mes, forma_pago having count(*) > 1
union all
select 'ev_cbd_zonas' as model, concat(mes, ' ', cast(puesto as varchar)) as key, count(*) as n
from {{ ref('ev_cbd_zonas') }} group by mes, puesto having count(*) > 1
union all
select 'ev_tarifas_altas' as model, concat(mes, ' ', periodo, ' ', cast(puesto as varchar)) as key, count(*) as n
from {{ ref('ev_tarifas_altas') }} group by mes, periodo, puesto having count(*) > 1
union all
select 'ev_calidad' as model, concat(mes, ' ', rol) as key, count(*) as n
from {{ ref('ev_calidad') }} group by mes, rol having count(*) > 1
union all
select 'ev_reglas' as model, concat(mes, ' ', regla) as key, count(*) as n
from {{ ref('ev_reglas') }} group by mes, regla having count(*) > 1
