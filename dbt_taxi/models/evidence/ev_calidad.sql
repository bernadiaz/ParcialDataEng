-- Grain: two rows per comparison (one per period): the quality gate of each file. The counts come from the quality
-- report of the run that loaded the month (RAW.QUALITY_SUMMARY). When that report is missing, or its accepted rows
-- are not the ones in the warehouse, they come from the warehouse itself (fuente = 'warehouse'): accepted rows in
-- fact_trips and quarantined rows in RAW.YELLOW_QUARANTINE, without the warnings.
with cuarentena as (

    select year, month, count(*) as filas
    from {{ source('raw', 'yellow_quarantine') }}
    group by year, month

),

unidos as (

    select
        p.mes,
        p.anio,
        p.mes_num,
        p.periodo,
        p.rol,
        p.anio_periodo,
        f.trips as aceptadas,
        coalesce(q.filas, 0) as filas_cuarentena,
        r.source_file,
        r.file_rows,
        r.rows_read,
        r.rows_quarantined,
        r.rows_with_warnings,
        r.reconciled,
        case when r.rows_accepted = f.trips then 'reporte' else 'warehouse' end as fuente
    from {{ ref('ev_periodos') }} as p
    inner join {{ ref('agg_month_profile') }} as f on f.year = p.anio_periodo and f.month = p.mes_num
    left join cuarentena as q on q.year = p.anio_periodo and q.month = p.mes_num
    left join {{ source('raw', 'quality_summary') }} as r on r.year = p.anio_periodo and r.month = p.mes_num

),

conteos as (

    select
        unidos.*,
        case when fuente = 'reporte' then rows_read else aceptadas + filas_cuarentena end as leidas,
        case when fuente = 'reporte' then rows_quarantined else filas_cuarentena end as cuarentena,
        case when fuente = 'reporte' then rows_with_warnings end as con_advertencias
    from unidos

)

select
    mes,
    anio,
    mes_num,
    periodo,
    rol,
    anio_periodo,
    coalesce(source_file, concat('yellow_tripdata_', periodo, '.parquet')) as archivo,
    file_rows as filas_archivo,
    leidas,
    aceptadas,
    cuarentena,
    {{ pct_of('cuarentena', 'leidas') }} as pct_cuarentena,
    con_advertencias,
    {{ pct_of('con_advertencias', 'leidas') }} as pct_advertencias,
    case when leidas = aceptadas + cuarentena and coalesce(reconciled, true) then 'sí' else 'no' end as reconcilia,
    fuente
from conteos
