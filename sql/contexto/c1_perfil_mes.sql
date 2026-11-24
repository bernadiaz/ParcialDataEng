-- Contexto 1: perfil de cada mes (volumen, ingresos, tarifas, distancia, mezcla de pagos y peaje CBD).
-- Lo usa src/interpretacion.py para redactar las interpretaciones; no es una pregunta del examen.
-- Sale de marts.agg_month_profile, la misma tabla de la que salen los tableros de respaldo de Superset.
select *
from marts.agg_month_profile
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
