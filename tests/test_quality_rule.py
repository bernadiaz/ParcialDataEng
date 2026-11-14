"""Regla de calidad sobre datos sintéticos + reconciliación de conteos."""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.calidad import (
    BUSINESS_COLS,
    accepted_path,
    load_rules,
    process_month,
    quarantine_path,
)
from src.config import Settings
from src.ingesta_airbyte import MonthRef


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        env="dev",
        mes="2025-03",
        data_dir=tmp_path,
        s3_endpoint_url=None,
        s3_access_key_id=None,
        s3_secret_access_key=None,
        s3_bucket="x",
        s3_region="us-east-1",
        s3_use_ssl=False,
        s3_path_style=True,
        s3_raw_prefix="raw",
        s3_control_prefix="control",
        object_store="fs",
        duckdb_threads=1,
        duckdb_memory_limit="512MB",
        max_distance_miles=100,
        cbd_fee_missing_strategy="null",
        ingest_max_retries=3,
        skip_snowflake=True,
        skip_dbt=True,
        airbyte_enabled=False,
        snowflake_account=None,
        snowflake_user=None,
        snowflake_warehouse=None,
        snowflake_database=None,
        snowflake_schema_raw="RAW",
        snowflake_schema_staging="STAGING",
        snowflake_schema_marts="MARTS",
    )


def _write_synthetic(settings: Settings) -> MonthRef:
    """4 filas: 1 ok, 1 R03 distancia, 1 R04 total neg, 1 R05 warn (aceptada)."""
    ref = MonthRef(2025, 3)
    zones = settings.data_dir / "raw" / "zones" / "taxi_zone_lookup.csv"
    zones.parent.mkdir(parents=True)
    zones.write_text(
        "LocationID,Borough,Zone,service_zone\n1,EWR,Newark Airport,EWR\n"
        "2,Queens,Jamaica Bay,Boro Zone\n",
        encoding="utf-8",
    )

    stg = (
        settings.data_dir
        / "staging"
        / "yellow"
        / "year=2025"
        / "month=03"
        / "part.parquet"
    )
    stg.parent.mkdir(parents=True)

    con = duckdb.connect()
    con.execute(
        """
        COPY (
          SELECT * FROM (
            VALUES
              -- ok
              (1::BIGINT, TIMESTAMP '2025-03-10 10:00:00', TIMESTAMP '2025-03-10 10:20:00',
               1::BIGINT, 2.5::DOUBLE, 1::BIGINT, 'N', 1::BIGINT, 2::BIGINT, 1::BIGINT,
               10.0, 0.5, 0.5, 2.0, 0.0, 0.3, 13.3, 2.5, 0.0, 0.0,
               'synth.parquet', 2025, 3),
              -- R03 distance <= 0
              (1::BIGINT, TIMESTAMP '2025-03-10 11:00:00', TIMESTAMP '2025-03-10 11:20:00',
               1::BIGINT, 0.0::DOUBLE, 1::BIGINT, 'N', 1::BIGINT, 2::BIGINT, 1::BIGINT,
               10.0, 0.5, 0.5, 2.0, 0.0, 0.3, 13.3, 2.5, 0.0, 0.0,
               'synth.parquet', 2025, 3),
              -- R04 total_amount < 0
              (1::BIGINT, TIMESTAMP '2025-03-10 12:00:00', TIMESTAMP '2025-03-10 12:20:00',
               1::BIGINT, 3.0::DOUBLE, 1::BIGINT, 'N', 1::BIGINT, 2::BIGINT, 1::BIGINT,
               10.0, 0.5, 0.5, 2.0, 0.0, 0.3, -5.0, 2.5, 0.0, 0.0,
               'synth.parquet', 2025, 3),
              -- R05 warn only (passenger_count=0) → accepted
              (1::BIGINT, TIMESTAMP '2025-03-10 13:00:00', TIMESTAMP '2025-03-10 13:20:00',
               0::BIGINT, 2.0::DOUBLE, 1::BIGINT, 'N', 1::BIGINT, 2::BIGINT, 1::BIGINT,
               10.0, 0.5, 0.5, 2.0, 0.0, 0.3, 13.3, 2.5, 0.0, 0.0,
               'synth.parquet', 2025, 3)
          ) AS v(
            vendor_id, tpep_pickup_datetime, tpep_dropoff_datetime,
            passenger_count, trip_distance, ratecode_id, store_and_fwd_flag,
            pu_location_id, do_location_id, payment_type,
            fare_amount, extra, mta_tax, tip_amount, tolls_amount,
            improvement_surcharge, total_amount, congestion_surcharge,
            airport_fee, cbd_congestion_fee,
            source_file, source_year, source_month
          )
        ) TO ? (FORMAT PARQUET)
        """,
        [str(stg)],
    )
    return ref


def test_rules_yaml_has_at_least_8():
    rules = load_rules()
    assert len(rules) >= 8
    assert {r.id for r in rules} >= {f"R0{i}" for i in range(1, 9)}


def test_r03_rejects_nonpositive_distance(tmp_path: Path):
    settings = _settings(tmp_path)
    ref = _write_synthetic(settings)
    con = duckdb.connect()
    con.execute("SET memory_limit='512MB'")
    summary = process_month(
        con=con, settings=settings, ref=ref, rules=load_rules()
    )

    assert summary["rows_read"] == 4
    assert summary["rows_quarantine"] == 2  # R03 + R04
    assert summary["rows_accepted"] == 2  # ok + R05 warn
    assert summary["reconciled"] is True
    assert summary["per_rule"]["R03"] == 1
    assert summary["per_rule"]["R04"] == 1
    assert summary["per_rule"]["R05"] == 1

    # R05 no descarta: quality_flags en aceptadas
    flags = con.execute(
        "SELECT quality_flags FROM read_parquet(?) WHERE passenger_count = 0",
        [str(accepted_path(settings, ref))],
    ).fetchone()[0]
    assert "R05" in flags

    violated = con.execute(
        "SELECT violated_rules FROM read_parquet(?)",
        [str(quarantine_path(settings, ref))],
    ).fetchall()
    joined = "|".join(v[0] for v in violated)
    assert "R03" in joined and "R04" in joined


def test_reconciliation_identity(tmp_path: Path):
    settings = _settings(tmp_path)
    ref = _write_synthetic(settings)
    con = duckdb.connect()
    summary = process_month(
        con=con, settings=settings, ref=ref, rules=load_rules()
    )
    assert (
        summary["rows_read"]
        == summary["rows_accepted"] + summary["rows_quarantine"]
    )
