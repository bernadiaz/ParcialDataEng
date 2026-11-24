"""A small DuckDB warehouse for the report and dashboard tests: synthetic fact and dimensions, and the REAL dbt models of the
monthly aggregates and of the evidence, rendered from dbt_taxi/ (so a mistake in their SQL fails here, without dbt)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import jinja2
import yaml

from src import load_snowflake
from src.config import ROOT, Settings

DBT = ROOT / "dbt_taxi"
AGGREGATES = ("agg_month_profile", "agg_zone_month", "agg_hour_month", "agg_day", "agg_payment_month", "agg_airport_month",
              "top_fare_trips")
EVIDENCE = ("ev_comparaciones", "ev_periodos", "ev_cobertura", "ev_zonas", "ev_boroughs", "ev_horas", "ev_dias", "ev_dias_semana",
            "ev_pagos", "ev_cbd_zonas", "ev_tarifas_altas", "ev_calidad", "ev_reglas", "ev_esquema", "ev_indicadores")

ZONES = [(1, "EWR", "Newark Airport"), (132, "Queens", "JFK Airport"), (138, "Queens", "LaGuardia Airport"),
         (161, "Manhattan", "Midtown Center"), (237, "Manhattan", "Upper East Side South"),
         (61, "Brooklyn", "Crown Heights North"), (264, "Unknown", "N/A"),
         (901, "Bronx", "Zona de prueba 1"), (902, "Bronx", "Zona de prueba 2"), (903, "Bronx", "Zona de prueba 3"),
         (904, "Bronx", "Zona de prueba 4"), (905, "Bronx", "Zona de prueba 5")]  # 12 rows: ev_cobertura numbers the months with them


def dbt_vars() -> dict[str, Any]:
    return yaml.safe_load((DBT / "dbt_project.yml").read_text(encoding="utf-8"))["vars"]


def render(model: str, **overrides: Any) -> str:
    """The SQL of a dbt model for DuckDB on a full build (is_incremental() is false), with its refs in their schemas."""
    path = next(DBT.glob(f"models/*/{model}.sql"))
    env = jinja2.Environment()
    names = {**dbt_vars(), **overrides}
    context: dict[str, Any] = {
        "ref": lambda name: f"marts.{name}", "source": lambda schema, table: f"{schema}.{table}", "var": lambda name: names[name],
        "config": lambda **kwargs: "", "is_incremental": lambda: False, "target": type("Target", (), {"type": "duckdb"})(),
    }
    macros = env.from_string((DBT / "macros" / "evidence.sql").read_text(encoding="utf-8")).module
    context |= {name: getattr(macros, name) for name in ("mes_label", "pct_of", "var_pct", "zone_label", "payment_label", "dia_semana")}
    return env.from_string(path.read_text(encoding="utf-8")).render(**context)


def build_models(con: duckdb.DuckDBPyConnection, models: tuple[str, ...] = (*AGGREGATES, *EVIDENCE), **overrides: Any) -> None:
    for model in models:
        con.execute(f"CREATE OR REPLACE TABLE marts.{model} AS {render(model, **overrides)}")


def warehouse(settings: Settings, *, month: int = 2, years: tuple[int, int] = (2025, 2024)) -> Path:
    """February 2025 vs February 2024 by default (2024 is a leap year). cbd_min_zone_trips is lowered: the zones are small."""
    settings.warehouse_db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.warehouse_db))
    facts(con, month, years)
    con.close()
    target = load_snowflake.DuckDBWarehouse(settings)  # raw.quality_summary, raw.quality_rules and raw.schema_findings, empty
    target.ensure_objects()
    target.close()
    rebuild(settings)
    return settings.warehouse_db


def rebuild(settings: Settings) -> None:
    con = duckdb.connect(str(settings.warehouse_db))
    build_models(con, cbd_min_zone_trips=100)
    con.close()


def facts(con: duckdb.DuckDBPyConnection, month: int, years: tuple[int, int]) -> None:
    a, b = years
    con.execute("CREATE SCHEMA IF NOT EXISTS marts")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE OR REPLACE TABLE marts.dim_zone (location_id INTEGER, borough VARCHAR, zone VARCHAR, service_zone VARCHAR, "
                "is_airport BOOLEAN)")
    con.executemany("INSERT INTO marts.dim_zone VALUES (?, ?, ?, 'x', ?)", [(i, b_, z, z.endswith("Airport")) for i, b_, z in ZONES])
    con.execute(f"""
        CREATE OR REPLACE TABLE marts.fact_trips AS
        WITH base AS (
            SELECT y, i, day(last_day(make_date(y, {month}, 1))) AS days
            FROM range(2400) AS r(i) CROSS JOIN (VALUES ({a}), ({b})) AS t(y)
            WHERE i < CASE WHEN y = {a} THEN 2400 ELSE 2000 END
        ), trips AS (
            SELECT y AS year, {month} AS month, i,
                   make_date(y, {month}, CAST(i % days + 1 AS INTEGER)) AS pickup_date,
                   CAST((i * 7) % 24 AS INTEGER) AS pickup_hour,
                   CASE i % 10 WHEN 0 THEN 132 WHEN 1 THEN 138 WHEN 2 THEN 161 WHEN 3 THEN 161 WHEN 4 THEN 161
                               WHEN 5 THEN 237 WHEN 6 THEN 237 ELSE 61 END AS pu_location_id,
                   CASE i % 7 WHEN 0 THEN 132 ELSE 161 END AS do_location_id,
                   CASE WHEN y = {a} AND i % 9 = 0 THEN 0 WHEN i % 5 = 0 THEN 2 WHEN i % 41 = 0 THEN 3
                        WHEN i % 43 = 0 THEN 4 ELSE 1 END AS payment_type
            FROM base
        ), measured AS (
            SELECT *, CASE WHEN pu_location_id = 132 THEN 2 ELSE 1 END AS ratecode_id,
                   1 + (i % 13) * 0.7 + CASE WHEN pu_location_id IN (132, 138) THEN 12 ELSE 0 END AS trip_distance
            FROM trips
        ), priced AS (
            SELECT *, CASE WHEN year = {a} AND i = 17 THEN 9000.0 WHEN pu_location_id = 132 THEN 70.0
                           ELSE round(5 + trip_distance * 2.8, 2) END AS fare_amount
            FROM measured
        )
        SELECT md5(year || '#' || i) AS trip_key, year, month, pickup_date, pickup_hour, isodow(pickup_date) AS pickup_dow,
               pu_location_id, do_location_id, payment_type, ratecode_id,
               CASE WHEN payment_type = 0 THEN NULL ELSE 1 END AS passenger_count,
               CAST(trip_distance AS DOUBLE) AS trip_distance, CAST(trip_distance * 3 AS DOUBLE) AS duration_min,
               CAST(fare_amount AS DOUBLE) AS fare_amount,
               CAST(CASE WHEN payment_type = 1 THEN round(fare_amount * 0.2, 2) ELSE 0 END AS DOUBLE) AS tip_amount,
               CAST(CASE WHEN payment_type = 1 THEN 20.0 ELSE 0 END AS DOUBLE) AS tip_pct,
               CAST(fare_amount + CASE WHEN payment_type = 1 THEN round(fare_amount * 0.2, 2) ELSE 0 END + 2.5 AS DOUBLE) AS total_amount,
               CAST(CASE WHEN year = {a} THEN CASE WHEN pu_location_id IN (161, 237) THEN 0.75 ELSE 0 END END AS DOUBLE) AS cbd_congestion_fee
        FROM priced""")
    con.execute("""
        CREATE OR REPLACE TABLE marts.agg_zone_hour AS
        SELECT pu_location_id, pickup_date, pickup_hour, year, month, count(*) AS trips,
               round(sum(total_amount), 2) AS total_revenue, round(avg(duration_min), 2) AS avg_duration_min
        FROM marts.fact_trips GROUP BY ALL""")
    con.execute(f"""
        CREATE OR REPLACE TABLE marts.dim_date AS
        SELECT CAST(d AS DATE) AS date_key, year(d) AS year, month(d) AS month, day(d) AS day_of_month,
               isodow(d) AS day_of_week_iso, dayname(d) AS day_name
        FROM (SELECT unnest(generate_series(make_date({b}, {month}, 1), last_day(make_date({b}, {month}, 1)), INTERVAL 1 DAY)) AS d
              UNION ALL
              SELECT unnest(generate_series(make_date({a}, {month}, 1), last_day(make_date({a}, {month}, 1)), INTERVAL 1 DAY)))""")
    con.execute(f"CREATE OR REPLACE TABLE raw.yellow_quarantine AS SELECT {a} AS year, {month} AS month, 'R03' AS violated_rules FROM range(90) "
                f"UNION ALL SELECT {b}, {month}, 'R04' FROM range(40)")
    con.execute("CREATE OR REPLACE TABLE marts.agg_quarantine_rule AS SELECT year, month, violated_rules AS rule_id, count(*) AS quarantined_rows "
                "FROM raw.yellow_quarantine GROUP BY ALL")


def publish_reports(settings: Settings, *, month: int = 2, years: tuple[int, int] = (2025, 2024)) -> None:
    """The quality and schema reports that the loader publishes, as if both months had been processed by this version."""
    con = duckdb.connect(str(settings.warehouse_db))
    for table in load_snowflake.QUALITY_TABLES:
        con.execute(f"DELETE FROM raw.{table}")
    for year, accepted, quarantined, warnings in ((years[0], 2400, 90, 300), (years[1], 2000, 40, 100)):
        con.execute("INSERT INTO raw.quality_summary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, 'ok', 'run')",
                    [year, month, f"{year}-{month:02d}", f"yellow_tripdata_{year}-{month:02d}.parquet", accepted + quarantined,
                     accepted + quarantined, accepted, quarantined, warnings])
        con.executemany("INSERT INTO raw.quality_rules VALUES (?, ?, ?, ?, ?, ?, ?, 'run')", [
            [year, month, "R03", "reject", "Distancia fuera de rango.", "x", 90 if year == years[0] else 0],
            [year, month, "R04", "reject", "Total faltante o negativo.", "x", 40 if year == years[1] else 0],
            [year, month, "R05", "warning", "Cantidad de pasajeros NULL o 0.", "x", warnings]])
        con.executemany("INSERT INTO raw.schema_findings VALUES (?, ?, ?, ?, ?, ?, ?, 'run')",
                        [[year, month, 1, "none", None, None, None]] if year == years[0] else
                        [[year, month, 1, "missing_optional", "cbd_congestion_fee", None, None],
                         [year, month, 2, "cast_failure", "passenger_count", None, 7]])
    con.close()
    rebuild(settings)
