-- FinOps queries run by `make finops` as the service user (role TAXI_PIPELINE).
-- Statements are split by the Snowflake connector, so ';' inside comments and strings is safe.

-- Credits per warehouse and day over the last 14 days (ACCOUNT_USAGE: up to ~3 h of latency)
-- The role reads it through IMPORTED PRIVILEGES on the SNOWFLAKE database (snowflake/setup.sql).
-- INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY would need the account-wide MONITOR USAGE privilege.
SELECT warehouse_name, TO_DATE(start_time) AS day,
       ROUND(SUM(credits_used), 4) AS credits_used,
       ROUND(SUM(credits_used_compute), 4) AS credits_compute,
       ROUND(SUM(credits_used_cloud_services), 4) AS credits_cloud_services
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -14, CURRENT_DATE())
  AND warehouse_name IN ('WH_TAXI_DEV', 'WH_TAXI_RUN')
GROUP BY 1, 2
ORDER BY 2 DESC, 1;

-- Queries and elapsed time per pipeline step, from the query_tag (project=nyc_taxi;env=...;owner=...;step=...)
-- Finished queries only: a running query has no final elapsed time.
-- warehouse_size is NULL for metadata-only statements (SHOW, PUT, DDL) that use no warehouse compute.
SELECT REGEXP_SUBSTR(query_tag, 'step=([^;]+)', 1, 1, 'e') AS step,
       warehouse_name,
       COALESCE(warehouse_size, 'none (metadata only)') AS warehouse_size,
       COUNT(*) AS queries,
       ROUND(SUM(total_elapsed_time) / 1000, 1) AS elapsed_seconds,
       ROUND(SUM(bytes_scanned) / POWER(1024, 3), 3) AS gb_scanned
FROM TABLE(NYC_TAXI.INFORMATION_SCHEMA.QUERY_HISTORY(RESULT_LIMIT => 10000))
WHERE query_tag LIKE 'project=nyc_taxi%'
  AND execution_status NOT IN ('RUNNING', 'QUEUED', 'BLOCKED', 'RESUMING_WAREHOUSE')
GROUP BY 1, 2, 3
ORDER BY elapsed_seconds DESC;

-- Storage of the project objects (staging models are views: no storage)
SELECT table_schema, table_name, table_type, row_count,
       ROUND(bytes / POWER(1024, 2), 1) AS mb, is_transient
FROM NYC_TAXI.INFORMATION_SCHEMA.TABLES
WHERE table_schema IN ('RAW', 'STAGING', 'MARTS')
ORDER BY bytes DESC NULLS LAST, table_schema, table_name;
