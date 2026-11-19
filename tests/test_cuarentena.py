"""Quarantine (exam Part 3): rejected rows keep their values, source and rules; table and lake copy are idempotent."""
from __future__ import annotations

import boto3
import duckdb
from moto import mock_aws

from src import calidad, ingesta_airbyte, load_snowflake
from src.config import Settings
from tests.conftest import JAN_2025, trip, write_tlc_parquet


def _month_with_rejects(settings: Settings) -> calidad.QualityResult:
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet",
                      [trip(), trip(trip_distance=0), trip(trip_distance=0, total_amount=-3.0)])
    return calidad.run_month(settings, JAN_2025)


def test_quarantine_keeps_the_row_its_source_and_the_violated_rules(settings, zones_file):
    result = _month_with_rejects(settings)

    assert (result.rows_read, result.rows_accepted, result.rows_quarantined) == (3, 1, 2)
    con = duckdb.connect()
    rows = con.execute(
        "SELECT trip_distance, total_amount, source_file, source_row_number, violated_rules "
        f"FROM read_parquet('{calidad.quarantine_file(settings, JAN_2025).as_posix()}', hive_partitioning = false) "
        "ORDER BY source_row_number").fetchall()
    con.close()
    assert [r[0] for r in rows] == [0.0, 0.0]                         # original values, untouched
    assert all(r[2] and r[3] is not None for r in rows)                # points back to the raw row
    assert [set(r[4].split(";")) >= {"R03"} for r in rows] == [True, True]
    assert calidad.quarantine_by_rule(settings, JAN_2025)["R03"] == 2
    assert calidad.quarantine_by_rule(settings, JAN_2025)["R04"] == 1


def test_quarantine_table_reload_replaces_the_month(settings, zones_file):
    _month_with_rejects(settings)

    first = load_snowflake.load_months(settings, [JAN_2025], include_trips=False)
    second = load_snowflake.load_months(settings, [JAN_2025], include_trips=False)

    q1 = next(r for r in first if r.table == "raw.yellow_quarantine")
    q2 = next(r for r in second if r.table == "raw.yellow_quarantine")
    assert (q1.rows_deleted, q1.rows_loaded) == (0, 2)
    assert (q2.rows_deleted, q2.rows_loaded) == (2, 2)                # replaced, never appended
    con = duckdb.connect(str(settings.warehouse_db), read_only=True)
    try:
        rows = con.execute("SELECT violated_rules, source_file, year, month FROM raw.yellow_quarantine").fetchall()
    finally:
        con.close()
    assert len(rows) == 2 and all(r[0] and r[1] and (r[2], r[3]) == (2025, 1) for r in rows)


@mock_aws
def test_quarantine_file_is_copied_to_the_lake_only_in_cloud_mode(settings, zones_file, monkeypatch):
    _month_with_rejects(settings)
    assert calidad.publish_quarantine(settings, JAN_2025) is None     # offline: local file only

    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name, value in {"WAREHOUSE": "snowflake", "INGEST_MODE": "direct", "S3_BUCKET": "nyc-taxi-test",
                        "AWS_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing"}.items():
        monkeypatch.setenv(name, value)
    cloud = Settings.from_env()
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    client.put_object(Bucket="nyc-taxi-test", Key="quarantine/yellow/year=2025/month=01/old.parquet", Body=b"x")

    uri = calidad.publish_quarantine(cloud, JAN_2025, s3=ingesta_airbyte.S3Store(cloud, client=client))

    key = "quarantine/yellow/year=2025/month=01/part-0.parquet"
    assert uri == f"s3://nyc-taxi-test/{key}"
    assert [o["Key"] for o in client.list_objects_v2(Bucket="nyc-taxi-test")["Contents"]] == [key]
    body = client.get_object(Bucket="nyc-taxi-test", Key=key)["Body"].read()
    assert body == calidad.quarantine_file(cloud, JAN_2025).read_bytes()
