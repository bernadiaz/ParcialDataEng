-- Grain: one row per comparison and indicator. Every figure of the month that the reports quote and that is not a row
-- of another ev_* model (zones, hours, payments...): value of the month, value of the same month of the previous
-- year, difference and change in %. Superset shows these rows; src/interpretacion.py writes the same figures from the
-- same marts, and src/evidencia.py checks that every figure of a report is shown by the charts it cites.
{%- set inicio = var('cbd_fee_start').split('-') %}
{%- set indicadores = [
    ('volumen', 'viajes', 'Viajes válidos', 'viajes', 'pa.trips', 'pb.trips'),
    ('volumen', 'recaudacion', 'Recaudación total (total_amount)', 'USD', 'pa.revenue', 'pb.revenue'),
    ('volumen', 'dias_del_mes', 'Días del mes', 'días', 'k.dias_mes', 'k.dias_anterior'),
    ('volumen', 'dias_con_viajes', 'Días con viajes', 'días', 'pa.days_with_trips', 'pb.days_with_trips'),
    ('volumen', 'viajes_calendario_anterior', 'Viajes del mes con el calendario del año anterior', 'viajes', 'k.viajes_calendario', 'pb.trips'),
    ('tarifa', 'tarifa_media', 'Tarifa media', 'USD', 'pa.avg_fare', 'pb.avg_fare'),
    ('tarifa', 'tarifa_media_sin_atipicas', 'Tarifa media sin tarifas mayores a US$ ' ~ var('fare_cap'), 'USD', 'pa.avg_fare_capped', 'pb.avg_fare_capped'),
    ('tarifa', 'tarifa_mediana', 'Tarifa mediana', 'USD', 'pa.median_fare', 'pb.median_fare'),
    ('tarifa', 'tarifa_maxima', 'Tarifa máxima', 'USD', 'pa.max_fare', 'pb.max_fare'),
    ('tarifa', 'tarifas_sobre_tope', 'Viajes con tarifa mayor a US$ ' ~ var('fare_cap'), 'viajes', 'pa.fares_over_cap', 'pb.fares_over_cap'),
    ('tarifa', 'tarifas_sobre_tope_total', 'Viajes con tarifa mayor a US$ ' ~ var('fare_cap') ~ ' en los dos meses', 'viajes', 'pa.fares_over_cap + pb.fares_over_cap', 'null'),
    ('viaje', 'distancia_media', 'Distancia media', 'millas', 'pa.avg_distance', 'pb.avg_distance'),
    ('viaje', 'pct_viajes_largos', 'Viajes de más de ' ~ var('long_trip_miles') ~ ' millas', '% de los viajes', 'pa.pct_long_trips', 'pb.pct_long_trips'),
    ('viaje', 'duracion_media', 'Duración media', 'minutos', 'pa.avg_duration_min', 'pb.avg_duration_min'),
    ('mezcla', 'participacion_flex', 'Participación de Flex Fare', '% de los viajes', pct_of('pa.flex_trips', 'pa.trips'), pct_of('pb.flex_trips', 'pb.trips')),
    ('mezcla', 'participacion_tarjeta', 'Participación de la tarjeta de crédito', '% de los viajes', pct_of('pa.card_trips', 'pa.trips'), pct_of('pb.card_trips', 'pb.trips')),
    ('mezcla', 'participacion_efectivo', 'Participación del efectivo', '% de los viajes', pct_of('pa.cash_trips', 'pa.trips'), pct_of('pb.cash_trips', 'pb.trips')),
    ('mezcla', 'tarifa_flex', 'Tarifa media Flex Fare', 'USD', 'pa.avg_fare_flex', 'pb.avg_fare_flex'),
    ('mezcla', 'tarifa_no_flex', 'Tarifa media sin Flex Fare', 'USD', 'pa.avg_fare_not_flex', 'pb.avg_fare_not_flex'),
    ('mezcla', 'tarifa_flex_sin_atipicas', 'Tarifa media Flex Fare, sin tarifas mayores a US$ ' ~ var('fare_cap'), 'USD', 'pa.avg_fare_flex_capped', 'pb.avg_fare_flex_capped'),
    ('mezcla', 'tarifa_no_flex_sin_atipicas', 'Tarifa media sin Flex Fare ni tarifas mayores a US$ ' ~ var('fare_cap'), 'USD', 'pa.avg_fare_not_flex_capped', 'pb.avg_fare_not_flex_capped'),
    ('mezcla', 'propina_tarjeta', 'Propina media con tarjeta de crédito', '% de la tarifa', 't.propina_media_pct_mes', 't.propina_media_pct_anterior'),
    ('aeropuertos', 'viajes_aeropuerto', 'Viajes que tocan JFK o LaGuardia', 'viajes', 'aa.airport_trips', 'ab.airport_trips'),
    ('aeropuertos', 'participacion_aeropuertos', 'Participación de los viajes de aeropuerto', '% de los viajes', pct_of('aa.airport_trips', 'pa.trips'), pct_of('ab.airport_trips', 'pb.trips')),
    ('aeropuertos', 'viajes_jfk', 'Viajes que tocan JFK', 'viajes', 'aa.jfk_trips', 'ab.jfk_trips'),
    ('aeropuertos', 'viajes_lga', 'Viajes que tocan LaGuardia', 'viajes', 'aa.lga_trips', 'ab.lga_trips'),
    ('aeropuertos', 'tarifa_media_aeropuerto', 'Tarifa media de los viajes de aeropuerto', 'USD', 'aa.avg_fare', 'ab.avg_fare'),
    ('aeropuertos', 'tarifa_media_aeropuerto_sin_atipicas', 'Tarifa media de aeropuerto sin tarifas mayores a US$ ' ~ var('fare_cap'), 'USD', 'aa.avg_fare_capped', 'ab.avg_fare_capped'),
    ('aeropuertos', 'tarifa_mediana_aeropuerto', 'Tarifa mediana de los viajes de aeropuerto', 'USD', 'aa.median_fare', 'ab.median_fare'),
    ('aeropuertos', 'tarifa_maxima_aeropuerto', 'Tarifa máxima de los viajes de aeropuerto', 'USD', 'aa.max_fare', 'ab.max_fare'),
    ('aeropuertos', 'tarifa_fija_jfk', 'Tarifa fija de JFK (mediana de RatecodeID 2)', 'USD', 'aa.jfk_flat_fare', 'ab.jfk_flat_fare'),
    ('zonas', 'pickups', 'Pickups de todas las zonas', 'viajes', 'z.pickups_mes', 'z.pickups_anterior'),
    ('zonas', 'top10_viajes', 'Viajes del top 10 de zonas de cada mes', 'viajes', 'z.top10_viajes_mes', 'z.top10_viajes_anterior'),
    ('zonas', 'top10_participacion', 'Pickups que concentra el top 10 de cada mes', '% de los pickups', pct_of('z.top10_viajes_mes', 'z.pickups_mes'), pct_of('z.top10_viajes_anterior', 'z.pickups_anterior')),
    ('zonas', 'top10_zonas', 'Zonas en el top 10', 'zonas', 'z.top10_zonas_mes', 'z.top10_zonas_anterior'),
    ('zonas', 'top10_manhattan', 'Zonas del top 10 en Manhattan', 'zonas', 'z.top10_manhattan_mes', 'z.top10_manhattan_anterior'),
    ('zonas', 'top10_crecen', 'Zonas del top 10 que crecen (' ~ var('stable_pct') ~ ' % o más)', 'zonas', 'z.top10_crecen', 'null'),
    ('zonas', 'top10_caen', 'Zonas del top 10 que caen (' ~ var('stable_pct') ~ ' % o más)', 'zonas', 'z.top10_caen', 'null'),
    ('zonas', 'top10_estables', 'Zonas del top 10 que se mantienen', 'zonas', 'z.top10_estables', 'null'),
    ('zonas', 'top10_entran', 'Zonas que entran al top 10', 'zonas', 'z.top10_entran', 'null'),
    ('zonas', 'top10_salen', 'Zonas que salen del top 10', 'zonas', 'z.top10_salen', 'null'),
    ('horas', 'hora_mayor_ingreso', 'Hora con mayor ingreso promedio por viaje', 'hora', 'mh.hora_mes', 'mh.hora_anterior'),
    ('horas', 'ingreso_hora_mayor', 'Ingreso promedio por viaje en esa hora', 'USD', 'mh.ingreso_mes', 'mh.ingreso_anterior'),
    ('horas', 'viajes_hora_mayor', 'Viajes en esa hora', 'viajes', 'mh.viajes_hora_mes', 'mh.viajes_hora_anterior'),
    ('horas', 'hora_pico', 'Hora pico de demanda', 'hora', 'hp.hora_mes', 'hp.hora_anterior'),
    ('horas', 'viajes_hora_pico', 'Viajes en la hora pico', 'viajes', 'hp.viajes_mes', 'hp.viajes_anterior'),
    ('peaje', 'viajes_con_peaje', 'Viajes con cbd_congestion_fee > 0', 'viajes', 'case when pa.cbd_fee_reported > 0 then pa.trips_with_cbd_fee end', 'case when pb.cbd_fee_reported > 0 then pb.trips_with_cbd_fee end'),
    ('peaje', 'pct_con_peaje', 'Proporción de viajes con cbd_congestion_fee > 0', '% de los viajes', 'case when pa.cbd_fee_reported > 0 then ' ~ pct_of('pa.trips_with_cbd_fee', 'pa.trips') ~ ' end', 'case when pb.cbd_fee_reported > 0 then ' ~ pct_of('pb.trips_with_cbd_fee', 'pb.trips') ~ ' end'),
    ('peaje', 'peaje_medio', 'Cobro medio (cbd_congestion_fee > 0)', 'USD', 'pa.avg_cbd_fee', 'pb.avg_cbd_fee'),
    ('peaje', 'peaje_minimo', 'Cobro mínimo (cbd_congestion_fee > 0)', 'USD', 'pa.min_cbd_fee', 'pb.min_cbd_fee'),
    ('peaje', 'viajes_con_dato_peaje', 'Viajes donde la columna trae un valor', 'viajes', 'pa.cbd_fee_reported', 'pb.cbd_fee_reported'),
    ('peaje', 'pct_viajes_antes_peaje', 'Viajes del mes anteriores al inicio del peaje (' ~ var('cbd_fee_start') ~ ')', '% de los viajes', pct_of('ia.viajes_antes', 'ia.viajes'), pct_of('ib.viajes_antes', 'ib.viajes')),
    ('peaje', 'pct_con_peaje_antes', 'Viajes con peaje antes del inicio (' ~ var('cbd_fee_start') ~ ')', '% de esos viajes', pct_of('ia.con_peaje_antes', 'ia.viajes_antes'), pct_of('ib.con_peaje_antes', 'ib.viajes_antes')),
    ('peaje', 'pct_con_peaje_desde', 'Viajes con peaje desde el inicio (' ~ var('cbd_fee_start') ~ ')', '% de esos viajes', pct_of('ia.con_peaje_desde', 'ia.viajes_desde'), pct_of('ib.con_peaje_desde', 'ib.viajes_desde')),
    ('calidad', 'filas_cuarentena', 'Filas en cuarentena', 'filas', 'q.cuarentena_mes', 'q.cuarentena_anterior'),
    ('calidad', 'pct_cuarentena', 'Proporción de filas en cuarentena', '% de las filas leídas', 'q.pct_cuarentena_mes', 'q.pct_cuarentena_anterior'),
] %}
with zonas as (

    select
        mes,
        sum(viajes_mes) as pickups_mes,
        sum(viajes_anterior) as pickups_anterior,
        sum(case when puesto_mes <= 10 then viajes_mes end) as top10_viajes_mes,
        sum(case when puesto_anterior <= 10 then viajes_anterior end) as top10_viajes_anterior,
        sum(case when puesto_mes <= 10 then 1 else 0 end) as top10_zonas_mes,
        sum(case when puesto_anterior <= 10 then 1 else 0 end) as top10_zonas_anterior,
        sum(case when puesto_mes <= 10 and borough = 'Manhattan' then 1 else 0 end) as top10_manhattan_mes,
        sum(case when puesto_anterior <= 10 and borough = 'Manhattan' then 1 else 0 end) as top10_manhattan_anterior,
        sum(case when puesto_mes <= 10 and variacion_pct >= {{ var('stable_pct') }} then 1 else 0 end) as top10_crecen,
        sum(case when puesto_mes <= 10 and variacion_pct <= -{{ var('stable_pct') }} then 1 else 0 end) as top10_caen,
        sum(case when puesto_mes <= 10 and variacion_pct > -{{ var('stable_pct') }}
            and variacion_pct < {{ var('stable_pct') }} then 1 else 0 end) as top10_estables,
        sum(case when puesto_mes <= 10 and (puesto_anterior is null or puesto_anterior > 10) then 1 else 0 end) as top10_entran,
        sum(case when puesto_anterior <= 10 and (puesto_mes is null or puesto_mes > 10) then 1 else 0 end) as top10_salen
    from {{ ref('ev_zonas') }}
    group by mes

),

mejor_hora as (

    select
        mes,
        max(case when puesto_mes = 1 then hora end) as hora_mes,
        max(case when puesto_mes = 1 then ingreso_viaje_mes end) as ingreso_mes,
        max(case when puesto_mes = 1 then viajes_mes end) as viajes_hora_mes,
        max(case when puesto_anterior = 1 then hora end) as hora_anterior,
        max(case when puesto_anterior = 1 then ingreso_viaje_anterior end) as ingreso_anterior,
        max(case when puesto_anterior = 1 then viajes_anterior end) as viajes_hora_anterior
    from {{ ref('ev_horas') }}
    group by mes

),

picos as (

    select
        mes,
        hora,
        viajes_mes,
        viajes_anterior,
        row_number() over (partition by mes order by viajes_mes desc nulls last, hora) as orden_mes,
        row_number() over (partition by mes order by viajes_anterior desc nulls last, hora) as orden_anterior
    from {{ ref('ev_horas') }}

),

hora_pico as (

    select
        mes,
        max(case when orden_mes = 1 then hora end) as hora_mes,
        max(case when orden_mes = 1 then viajes_mes end) as viajes_mes,
        max(case when orden_anterior = 1 then hora end) as hora_anterior,
        max(case when orden_anterior = 1 then viajes_anterior end) as viajes_anterior
    from picos
    group by mes

),

calendario as (

    select
        mes,
        sum(dias_mes) as dias_mes,
        sum(dias_anterior) as dias_anterior,
        sum(viajes_con_calendario_anterior) as viajes_calendario
    from {{ ref('ev_dias_semana') }}
    group by mes

),

-- CBD toll before and since its first day: only for the month when it started.
inicio_peaje as (

    select
        year,
        month,
        sum(trips) as viajes,
        sum(case when pickup_date < cast('{{ var('cbd_fee_start') }}' as date) then trips end) as viajes_antes,
        sum(case when pickup_date < cast('{{ var('cbd_fee_start') }}' as date) then trips_with_cbd_fee end) as con_peaje_antes,
        sum(case when pickup_date >= cast('{{ var('cbd_fee_start') }}' as date) then trips end) as viajes_desde,
        sum(case when pickup_date >= cast('{{ var('cbd_fee_start') }}' as date) then trips_with_cbd_fee end) as con_peaje_desde
    from {{ ref('agg_day') }}
    where year = {{ inicio[0] | int }} and month = {{ inicio[1] | int }}
    group by year, month

),

tarjeta as (

    select mes, propina_media_pct_mes, propina_media_pct_anterior
    from {{ ref('ev_pagos') }}
    where payment_type = 1

),

calidad as (

    select
        mes,
        max(case when rol = 'mes' then cuarentena end) as cuarentena_mes,
        max(case when rol = 'anterior' then cuarentena end) as cuarentena_anterior,
        max(case when rol = 'mes' then pct_cuarentena end) as pct_cuarentena_mes,
        max(case when rol = 'anterior' then pct_cuarentena end) as pct_cuarentena_anterior
    from {{ ref('ev_calidad') }}
    group by mes

),

base as (

    select
        c.mes,
        c.anio,
        c.mes_num
        {%- for grupo, id, etiqueta, unidad, del_mes, del_anterior in indicadores %},
        cast({{ del_mes }} as double) as {{ id }}__mes,
        cast({{ del_anterior }} as double) as {{ id }}__ant
        {%- endfor %}
    from {{ ref('ev_comparaciones') }} as c
    inner join {{ ref('agg_month_profile') }} as pa on pa.year = c.anio and pa.month = c.mes_num
    inner join {{ ref('agg_month_profile') }} as pb on pb.year = c.anio_anterior and pb.month = c.mes_num
    left join {{ ref('agg_airport_month') }} as aa on aa.year = c.anio and aa.month = c.mes_num
    left join {{ ref('agg_airport_month') }} as ab on ab.year = c.anio_anterior and ab.month = c.mes_num
    left join inicio_peaje as ia on ia.year = c.anio and ia.month = c.mes_num
    left join inicio_peaje as ib on ib.year = c.anio_anterior and ib.month = c.mes_num
    left join zonas as z on z.mes = c.mes
    left join mejor_hora as mh on mh.mes = c.mes
    left join hora_pico as hp on hp.mes = c.mes
    left join calendario as k on k.mes = c.mes
    left join tarjeta as t on t.mes = c.mes
    left join calidad as q on q.mes = c.mes

),

filas as (
{% for grupo, id, etiqueta, unidad, del_mes, del_anterior in indicadores %}
    select
        mes, anio, mes_num, {{ loop.index }} as orden, '{{ grupo }}' as grupo, '{{ id }}' as indicador_id,
        '{{ etiqueta }}' as indicador, '{{ unidad }}' as unidad,
        {{ id }}__mes as valor_mes, {{ id }}__ant as valor_anterior
    from base
    {% if not loop.last %}union all{% endif %}
{%- endfor %}

)

select
    filas.*,
    valor_mes - valor_anterior as variacion,
    {{ var_pct('valor_mes', 'valor_anterior') }} as variacion_pct
from filas
