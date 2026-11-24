-- Grain: one row per comparison, period and schema finding: what each TLC file brought compared with
-- contracts/yellow_schema.yaml and what the pipeline did about it (RAW.SCHEMA_FINDINGS). The rows with tipo =
-- 'total_...' add up the findings of a kind (values that could not be converted, columns with another type...).
with hallazgos as (

    select
        p.mes,
        p.anio,
        p.mes_num,
        p.periodo,
        p.rol,
        p.anio_periodo,
        f.finding,
        f.column_name,
        f.detail,
        f.affected_values,
        f.item_order
    from {{ ref('ev_periodos') }} as p
    inner join {{ source('raw', 'schema_findings') }} as f on f.year = p.anio_periodo and f.month = p.mes_num

),

con_totales as (

    select mes, anio, mes_num, periodo, rol, anio_periodo, finding, column_name, detail, affected_values, item_order
    from hallazgos
    union all
    select
        mes, anio, mes_num, periodo, rol, anio_periodo,
        concat('total_', finding) as finding,
        cast(null as varchar) as column_name,
        cast(null as varchar) as detail,
        case when finding = 'type_mismatch' then count(*) else sum(affected_values) end as affected_values,
        1000 as item_order
    from hallazgos
    where finding in ('type_mismatch', 'cast_failure', 'unresolved_264', 'unresolved_265')
    group by mes, anio, mes_num, periodo, rol, anio_periodo, finding

)

select
    mes,
    anio,
    mes_num,
    periodo,
    rol,
    anio_periodo,
    finding as tipo,
    case finding
        when 'none' then 'Coincide con el contrato (mismas columnas y tipos)'
        when 'missing_optional' then 'Columna opcional ausente: queda en NULL'
        when 'new_column' then 'Columna nueva: se ignora y se reporta'
        when 'type_mismatch' then 'Guardada con otro tipo: se convierte con TRY_CAST'
        when 'cast_failure' then 'Valores que no se pudieron convertir: quedan en NULL'
        when 'null_violation' then 'NULL en una columna obligatoria'
        when 'value_mapped' then 'Códigos de texto traducidos a los códigos actuales'
        when 'derived_zone' then 'Zona derivada de las coordenadas (formato anterior a 2011)'
        when 'unresolved_264' then 'Extremos sin coordenada: zona 264 Unknown'
        when 'unresolved_265' then 'Extremos fuera de toda zona: 265 Outside of NYC'
        when 'total_type_mismatch' then 'Total de columnas guardadas con otro tipo'
        when 'total_cast_failure' then 'Total de valores que no se pudieron convertir'
        when 'total_unresolved_264' then 'Total de extremos sin coordenada (zona 264)'
        when 'total_unresolved_265' then 'Total de extremos fuera de toda zona (265)'
        else finding
    end as novedad,
    column_name as columna,
    detail as detalle,
    cast(affected_values as bigint) as valores,
    item_order as orden
from con_totales
