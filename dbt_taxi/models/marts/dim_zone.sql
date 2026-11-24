-- Grain: one row per TLC LocationID (265). Zone names are not unique (Corona is 56 and 57,
-- Governor's Island is 103-105), so queries group by location_id and show the name.
select
    location_id,
    borough,
    zone,
    service_zone,
    zone in ('JFK Airport', 'LaGuardia Airport', 'Newark Airport') as is_airport
from {{ ref('stg_taxi_zones') }}
