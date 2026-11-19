-- Contexto 10 (respaldo): filas en cuarentena por regla de rechazo y año (marts.agg_quarantine_rule).
select year, rule_id, quarantined_rows
from marts.agg_quarantine_rule
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
