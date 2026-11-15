-- Grain: one row per month (year, month) and violated reject rule.
-- quarantined_rows counts the quarantined rows that violated the rule. A row can violate several
-- rules (violated_rules = 'R03;R04'), so the rule counts of a month add up to more than its quarantine.
-- Small table (a few rows per month): rebuilt on every run.
{% if target.type == 'snowflake' %}
select
    q.year,
    q.month,
    trim(r.value) as rule_id,
    count(*) as quarantined_rows
from {{ source('raw', 'yellow_quarantine') }} as q,
     lateral split_to_table(q.violated_rules, ';') as r
group by 1, 2, 3
{% else %}
select
    year,
    month,
    trim(rule_id) as rule_id,
    count(*) as quarantined_rows
from (
    select year, month, unnest(string_split(violated_rules, ';')) as rule_id
    from {{ source('raw', 'yellow_quarantine') }}
) as rules
group by 1, 2, 3
{% endif %}
