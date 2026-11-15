"""NYC Taxi pipeline: Airbyte -> S3 -> DuckDB quality gate -> Snowflake + dbt.

Modules (one per pipeline step, each runnable with ``python -m src.<module>``):
    config            settings from .env, months, paths, control database, step metrics
    ingesta_airbyte   Part 1: Airbyte sync to S3, SHA-256 verification, ingestion_log
    esquema           Part 2: schema contract, snake_case, month unification
    calidad           Part 3: quality rules, quarantine, reports, reconciliation
    load_snowflake    Part 4/5 bridge: idempotent month load into the warehouse RAW layer
    resultados        Part 5: q1..q6 against the marts -> RESULTADOS.md
    exploracion       data exploration behind the R03/R09 thresholds
    demos             oral defense helpers (idempotency, quarantine, quality report, FinOps)
"""
