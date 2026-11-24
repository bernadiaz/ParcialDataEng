-- Contexto 11: qué trajo cada archivo de la TLC comparado con el contrato de esquema (marts.ev_esquema, la tabla de Superset).
select *
from marts.ev_esquema
where mes = '${MES}'
order by rol, orden
