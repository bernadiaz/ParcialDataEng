-- Contexto 10: filas que violan cada regla de calidad en los dos meses (marts.ev_reglas, la tabla de Superset).
select *
from marts.ev_reglas
where mes = '${MES}'
