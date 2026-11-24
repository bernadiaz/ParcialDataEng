-- Contexto 7: viajes que empiezan o terminan en JFK o LaGuardia (misma definición que Q5): totales por aeropuerto,
-- tarifa media, mediana, media sin atípicos, tarifa máxima y la mediana de la tarifa fija de JFK (RatecodeID 2).
select *
from marts.agg_airport_month
where month = ${MONTH} and year in (${YEAR}, ${CMP_YEAR})
