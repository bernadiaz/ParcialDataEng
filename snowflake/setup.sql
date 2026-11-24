-- =============================================================================================
-- One-time Snowflake setup for the NYC Taxi pipeline (run in a Snowsight worksheet as ACCOUNTADMIN).
-- FinOps (plan section 3): dedicated X-Small warehouses with 60 s auto-suspend, a monthly credit
-- quota, layered schemas, a transient staging schema, cost tags and a least-privilege role.
-- Run it before the first `make load-sf`, so every table is created and owned by TAXI_PIPELINE.
-- =============================================================================================
USE ROLE ACCOUNTADMIN;

-- 1. Warehouses: X-Small, suspended when idle. WH_TAXI_DEV for development, WH_TAXI_RUN for the exam run.
CREATE WAREHOUSE IF NOT EXISTS WH_TAXI_DEV
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  COMMENT = 'NYC Taxi pipeline - development';
CREATE WAREHOUSE IF NOT EXISTS WH_TAXI_RUN
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  COMMENT = 'NYC Taxi pipeline - exam run';

-- 2. Credit guardrail: notify at 75% and suspend both warehouses at 100% of 10 credits per month.
CREATE RESOURCE MONITOR IF NOT EXISTS RM_TAXI WITH CREDIT_QUOTA = 10 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 75 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE WH_TAXI_DEV SET RESOURCE_MONITOR = RM_TAXI;
ALTER WAREHOUSE WH_TAXI_RUN SET RESOURCE_MONITOR = RM_TAXI;

-- 3. Database and layers. STAGING is transient: no Fail-safe storage for rebuildable objects.
CREATE DATABASE IF NOT EXISTS NYC_TAXI COMMENT = 'NYC TLC yellow taxi - exam pipeline';
CREATE SCHEMA IF NOT EXISTS NYC_TAXI.RAW COMMENT = 'Accepted rows loaded from the DuckDB quality gate';
CREATE TRANSIENT SCHEMA IF NOT EXISTS NYC_TAXI.STAGING COMMENT = 'dbt staging views and intermediate objects';
CREATE SCHEMA IF NOT EXISTS NYC_TAXI.MARTS COMMENT = 'dbt star schema and aggregates';
CREATE SCHEMA IF NOT EXISTS NYC_TAXI.GOVERNANCE COMMENT = 'Cost tags';

-- 4. Cost tags (Enterprise edition): project / env / owner on the warehouses and the database.
CREATE TAG IF NOT EXISTS NYC_TAXI.GOVERNANCE.PROJECT ALLOWED_VALUES 'nyc_taxi';
CREATE TAG IF NOT EXISTS NYC_TAXI.GOVERNANCE.ENV ALLOWED_VALUES 'dev', 'exam';
CREATE TAG IF NOT EXISTS NYC_TAXI.GOVERNANCE.OWNER;
ALTER WAREHOUSE WH_TAXI_DEV SET TAG NYC_TAXI.GOVERNANCE.PROJECT = 'nyc_taxi', NYC_TAXI.GOVERNANCE.ENV = 'dev', NYC_TAXI.GOVERNANCE.OWNER = 'franco.herrera';
ALTER WAREHOUSE WH_TAXI_RUN SET TAG NYC_TAXI.GOVERNANCE.PROJECT = 'nyc_taxi', NYC_TAXI.GOVERNANCE.ENV = 'exam', NYC_TAXI.GOVERNANCE.OWNER = 'franco.herrera';
ALTER DATABASE NYC_TAXI SET TAG NYC_TAXI.GOVERNANCE.PROJECT = 'nyc_taxi', NYC_TAXI.GOVERNANCE.OWNER = 'franco.herrera';

-- 5. Least-privilege role used by the loader, dbt and the question runner.
CREATE ROLE IF NOT EXISTS TAXI_PIPELINE COMMENT = 'NYC Taxi pipeline';
GRANT ROLE TAXI_PIPELINE TO ROLE SYSADMIN;
GRANT USAGE, OPERATE ON WAREHOUSE WH_TAXI_DEV TO ROLE TAXI_PIPELINE;
GRANT USAGE, OPERATE ON WAREHOUSE WH_TAXI_RUN TO ROLE TAXI_PIPELINE;
GRANT USAGE ON DATABASE NYC_TAXI TO ROLE TAXI_PIPELINE;
GRANT USAGE, CREATE TABLE, CREATE VIEW, CREATE STAGE ON SCHEMA NYC_TAXI.RAW TO ROLE TAXI_PIPELINE;
GRANT USAGE, CREATE TABLE, CREATE VIEW ON SCHEMA NYC_TAXI.STAGING TO ROLE TAXI_PIPELINE;
GRANT USAGE, CREATE TABLE, CREATE VIEW ON SCHEMA NYC_TAXI.MARTS TO ROLE TAXI_PIPELINE;
-- `make finops`: credit and query history
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE TAXI_PIPELINE;
GRANT MONITOR ON WAREHOUSE WH_TAXI_DEV TO ROLE TAXI_PIPELINE;
GRANT MONITOR ON WAREHOUSE WH_TAXI_RUN TO ROLE TAXI_PIPELINE;

-- 6. Your personal user can also use the role in Snowsight.
--    The name is double-quoted: a user name like FRANCO.HERRERA.CLOUD@GMAIL.COM has dots, and
--    IDENTIFIER() would read it as database.schema.object ("Object does not exist").
SET MY_USER = '"' || CURRENT_USER() || '"';
GRANT ROLE TAXI_PIPELINE TO USER IDENTIFIER($MY_USER);

-- 7. REQUIRED: service user with a key pair. The loader, dbt, the questions and Superset use it.
--    `externalbrowser` only works when the account has a SAML identity provider (error 390190
--    otherwise), and password-only logins are being phased out.
-- Generate the key in Git Bash, outside the repo:
--   mkdir -p ~/.snowflake
--   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out ~/.snowflake/taxi_svc.p8 -nocrypt
--   openssl rsa -in ~/.snowflake/taxi_svc.p8 -pubout -out ~/.snowflake/taxi_svc.pub
-- Paste the public key body (taxi_svc.pub without the BEGIN/END lines) below, then run this block.
CREATE USER IF NOT EXISTS TAXI_SVC TYPE = SERVICE
  DEFAULT_ROLE = TAXI_PIPELINE DEFAULT_WAREHOUSE = WH_TAXI_DEV
  RSA_PUBLIC_KEY = '<PASTE_PUBLIC_KEY_BODY_HERE>'
  COMMENT = 'NYC Taxi pipeline: loader, dbt, questions, Superset';
GRANT ROLE TAXI_PIPELINE TO USER TAXI_SVC;
-- Check: DESC USER TAXI_SVC;  (RSA_PUBLIC_KEY_FP must not be empty)
