-- Contexto 9: control de calidad de cada archivo (leídas, aceptadas, cuarentena, advertencias). Es la tabla que
-- muestra Superset: marts.ev_calidad. fuente = 'warehouse' cuando no hay un reporte de calidad de esas filas.
select *
from marts.ev_calidad
where mes = '${MES}'
