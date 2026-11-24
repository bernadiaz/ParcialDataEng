-- Grain: one row per comparison and quality rule: rows that violate it in each month and their % of the rows read.
-- Reject rules always have a count (RAW.YELLOW_QUARANTINE as a fallback). Warning rules only have one when the
-- quality report of the month is in the warehouse (NULL otherwise: never 0 by default).
with reglas as (

    select rule_id, max(severity) as severidad, max(description) as descripcion, max(threshold) as umbral
    from {{ source('raw', 'quality_rules') }}
    group by rule_id
    union all
    select distinct a.rule_id, 'reject' as severidad, cast(null as varchar) as descripcion, cast(null as varchar) as umbral
    from {{ ref('agg_quarantine_rule') }} as a
    left join (select distinct rule_id from {{ source('raw', 'quality_rules') }}) as k on k.rule_id = a.rule_id
    where k.rule_id is null

),

por_periodo as (

    select
        c.mes,
        c.anio,
        c.mes_num,
        c.rol,
        c.leidas,
        r.rule_id,
        r.severidad,
        r.descripcion,
        r.umbral,
        case
            when c.fuente = 'reporte' then coalesce(v.violations, 0)
            when r.severidad = 'reject' then coalesce(q.quarantined_rows, 0)
        end as filas
    from {{ ref('ev_calidad') }} as c
    cross join reglas as r
    left join {{ source('raw', 'quality_rules') }} as v
        on v.year = c.anio_periodo and v.month = c.mes_num and v.rule_id = r.rule_id
    left join {{ ref('agg_quarantine_rule') }} as q
        on q.year = c.anio_periodo and q.month = c.mes_num and q.rule_id = r.rule_id

),

lado_a_lado as (

    select
        mes,
        anio,
        mes_num,
        rule_id as regla,
        max(severidad) as severidad,
        max(descripcion) as descripcion,
        max(umbral) as umbral,
        max(case when rol = 'mes' then filas end) as filas_mes,
        max(case when rol = 'anterior' then filas end) as filas_anterior,
        max(case when rol = 'mes' then {{ pct_of('filas', 'leidas') }} end) as pct_mes,
        max(case when rol = 'anterior' then {{ pct_of('filas', 'leidas') }} end) as pct_anterior
    from por_periodo
    group by mes, anio, mes_num, rule_id

)

select
    lado_a_lado.*,
    pct_mes - pct_anterior as cambio_pp
from lado_a_lado
