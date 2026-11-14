"""Transformación: derivados y replace de partición."""

from __future__ import annotations

from pathlib import Path

import duckdb

from src.config import Settings
from src.ingesta_airbyte import MonthRef
from src.transform import curated_path, partition_counts, transform_month


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
        metrics_enabled=False,
        pushgateway_url=None,
        snowflake_account=None,
        snowflake_user=None,
        snowflake_warehouse=None,
        snowflake_database=None,
        snowflake_schema_raw="RAW",
        snowflake_schema_staging="STAGING",
        snowflake_schema_marts="MARTS",
    )


def _write_zones(settings: Settings) -> None:
    zones = settings.data_dir / "raw" / "zones" / "taxi_zone_lookup.csv"
    zones.parent.mkdir(parents=True)
    zones.write_text(
        "LocationID,Borough,Zone,service_zone\n"
        "1,EWR,Newark Airport,EWR\n"
        "2,Queens,Jamaica Bay,Boro Zone\n",
        encoding="utf-8",
    )


def _write_accepted(settings: Settings, ref: MonthRef, pickup_day: int = 10) -> Path:
    acc = (
        settings.data_dir
        / "accepted"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / "part.parquet"
    )
    acc.parent.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
          SELECT
            1::BIGINT AS vendor_id,
            TIMESTAMP '{ref.year:04d}-{ref.month:02d}-{pickup_day:02d} 10:00:00'
              AS tpep_pickup_datetime,
            TIMESTAMP '{ref.year:04d}-{ref.month:02d}-{pickup_day:02d} 10:30:00'
              AS tpep_dropoff_datetime,
            1::BIGINT AS passenger_count,
            15.0::DOUBLE AS trip_distance,
            1::BIGINT AS ratecode_id,
            'N' AS store_and_fwd_flag,
            1::BIGINT AS pu_location_id,
            2::BIGINT AS do_location_id,
            1::BIGINT AS payment_type,
            20.0::DOUBLE AS fare_amount,
            0.0::DOUBLE AS extra,
            0.5::DOUBLE AS mta_tax,
            4.0::DOUBLE AS tip_amount,
            0.0::DOUBLE AS tolls_amount,
            0.3::DOUBLE AS improvement_surcharge,
            24.8::DOUBLE AS total_amount,
            0.0::DOUBLE AS congestion_surcharge,
            0.0::DOUBLE AS airport_fee,
            0.0::DOUBLE AS cbd_congestion_fee,
            'x.parquet' AS source_file,
            {ref.year} AS source_year,
            {ref.month} AS source_month,
            ''::VARCHAR AS quality_flags
        ) TO '{acc}' (FORMAT PARQUET)
        """
    )
    return acc


def test_derived_columns_and_zone_enrich(tmp_path: Path):
    settings = _settings(tmp_path)
    ref = MonthRef(2025, 3)
    _write_zones(settings)
    _write_accepted(settings, ref)
    con = duckdb.connect()
    n = transform_month(con=con, settings=settings, ref=ref)
    assert n == 1

    row = con.execute(
        """
        SELECT duration_min, avg_speed_mph, pickup_hour, tip_pct, pu_borough, do_zone
        FROM read_parquet(?)
        """,
        [str(curated_path(settings, ref))],
    ).fetchone()
    duration_min, speed, hour, tip_pct, pu_borough, do_zone = row
    assert abs(duration_min - 30.0) < 1e-6
    assert abs(speed - 30.0) < 1e-6
    assert hour == 10
    assert abs(tip_pct - 0.2) < 1e-6
    assert pu_borough == "EWR"
    assert do_zone == "Jamaica Bay"


def test_partition_replace_keeps_other_months(tmp_path: Path):
    settings = _settings(tmp_path)
    r_target, r_other = MonthRef(2025, 3), MonthRef(2024, 3)
    _write_zones(settings)
    _write_accepted(settings, r_target)
    _write_accepted(settings, r_other)

    con = duckdb.connect()
    transform_month(con=con, settings=settings, ref=r_target)
    transform_month(con=con, settings=settings, ref=r_other)
    before = partition_counts(settings)
    assert before["2024-03"] == 1
    assert before["2025-03"] == 1

    # reprocesar solo 2025-03
    transform_month(con=con, settings=settings, ref=r_target)
    after = partition_counts(settings)
    assert after["2024-03"] == before["2024-03"]
    assert after["2025-03"] == 1
