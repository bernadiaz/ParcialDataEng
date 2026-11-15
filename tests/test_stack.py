"""Two-command run (docker compose up -d + make all): Dagster history, Airbyte fallback, offline mode, clean."""
from __future__ import annotations

import socket

import boto3
import httpx
import pytest
from moto import mock_aws

from src import clean, dagster_instance, dashboards, ingesta_airbyte
from src.config import Settings, dbt_target
from src.ingesta_airbyte import IngestionError, Ingestor
from tests.conftest import JAN_2025, ZONES_CSV


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --- Dagster run history ------------------------------------------------------------------------------
@pytest.fixture
def dagster_home(tmp_path, monkeypatch):
    home = tmp_path / "dagster_home"
    monkeypatch.setenv("DAGSTER_HOME", str(home))
    monkeypatch.setenv("DAGSTER_PG_HOST", "127.0.0.1")
    monkeypatch.setenv("DAGSTER_PG_PORT", str(_free_port()))   # nothing listens there
    monkeypatch.delenv("DAGSTER_COMPUTE_LOGS_DIR", raising=False)
    return home


def test_without_docker_the_history_falls_back_to_sqlite(dagster_home, monkeypatch):
    monkeypatch.setenv("DAGSTER_STORAGE", "auto")
    assert dagster_instance.configure(quiet=True) == "sqlite"
    assert "storage:" not in (dagster_home / "dagster.yaml").read_text(encoding="utf-8")


def test_with_docker_the_history_goes_to_the_shared_postgres(dagster_home, monkeypatch):
    monkeypatch.setenv("DAGSTER_STORAGE", "auto")
    monkeypatch.setattr(dagster_instance, "postgres_ready", lambda *args, **kwargs: True)
    monkeypatch.setenv("DAGSTER_COMPUTE_LOGS_DIR", "/opt/dagster/compute_logs")
    assert dagster_instance.configure(quiet=True) == "postgres"
    text = (dagster_home / "dagster.yaml").read_text(encoding="utf-8")
    assert "hostname: {env: DAGSTER_PG_HOST}" in text and "port: {env: DAGSTER_PG_PORT}" in text
    assert "base_dir: {env: DAGSTER_COMPUTE_LOGS_DIR}" in text


def test_required_postgres_fails_loudly(dagster_home, monkeypatch):
    monkeypatch.setenv("DAGSTER_STORAGE", "postgres")
    monkeypatch.setattr(dagster_instance, "postgres_ready", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="never answered"):
        dagster_instance.configure(quiet=True)


# --- dbt target ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("env, expected", [
    ({"WAREHOUSE": "duckdb", "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"}, "duckdb"),
    ({"WAREHOUSE": "snowflake", "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"}, "snowflake_keypair"),
    ({"WAREHOUSE": "snowflake", "SNOWFLAKE_PRIVATE_KEY_PATH": ""}, "snowflake_browser"),
    ({"WAREHOUSE": "duckdb", "DBT_TARGET": "snowflake_keypair"}, "snowflake_keypair"),
])
def test_dbt_target_follows_the_warehouse(monkeypatch, env, expected):
    monkeypatch.delenv("DBT_TARGET", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert dbt_target() == expected


# --- ingestion ---------------------------------------------------------------------------------------------
def test_offline_mode_never_touches_s3(settings, monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "a-bucket-in-the-developer-env")
    offline = Settings.from_env()
    assert offline.offline
    assert Ingestor(offline, sleep=lambda s: None).s3 is None


@pytest.fixture
def hybrid_without_airbyte(tmp_path, monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name, value in {
        "DATA_DIR": str(tmp_path / "data"), "INGEST_MODE": "hybrid", "WAREHOUSE": "snowflake",
        "S3_BUCKET": "nyc-taxi-test", "AWS_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", "S3_RAW_PREFIX": "raw",
        "AIRBYTE_API_URL": "", "AIRBYTE_CLIENT_ID": "", "AIRBYTE_CLIENT_SECRET": "",
    }.items():
        monkeypatch.setenv(name, value)
    return Settings.from_env()


@mock_aws
def test_zones_fall_back_to_direct_when_airbyte_is_not_available(hybrid_without_airbyte, monkeypatch):
    monkeypatch.setenv("AIRBYTE_FALLBACK", "direct")
    settings = hybrid_without_airbyte
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=ZONES_CSV.encode())))
    Ingestor(settings, http=http, s3=ingesta_airbyte.S3Store(settings, client=client), sleep=lambda s: None).zones()

    body = client.get_object(Bucket="nyc-taxi-test", Key="raw/zones/taxi_zone_lookup.csv")["Body"].read()
    assert body == ZONES_CSV.encode()                                   # same S3 prefix, unmodified
    from src.config import control_db

    with control_db(settings) as con:
        assert con.execute("SELECT mode, action, status FROM ingestion_log").fetchall() == [("direct", "downloaded", "ok")]


@mock_aws
def test_airbyte_fallback_can_be_disabled(hybrid_without_airbyte, monkeypatch):
    monkeypatch.setenv("AIRBYTE_FALLBACK", "fail")
    settings = hybrid_without_airbyte
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    with pytest.raises(IngestionError, match="Airbyte is not available"):
        Ingestor(settings, s3=ingesta_airbyte.S3Store(settings, client=client), sleep=lambda s: None).zones()


# --- Superset offline copy ---------------------------------------------------------------------------------
def test_bi_copy_avoids_compression_that_superset_duckdb_cannot_read(settings):
    import duckdb

    settings.warehouse_db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.warehouse_db))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.dim_zone AS SELECT range::INTEGER AS location_id, "
                "'Zone ' || (range % 50) AS zone FROM range(20000)")
    con.execute("CREATE TABLE marts.fact_trips AS SELECT range AS id, 'key-' || range AS trip_key FROM range(100)")
    con.close()

    path = dashboards.export_bi_copy(settings)

    con = duckdb.connect(str(path), read_only=True)
    methods = {r[0] for r in con.execute(
        "SELECT compression FROM pragma_storage_info('marts.dim_zone') WHERE segment_type = 'VARCHAR'").fetchall()}
    assert "DICT_FSST" not in methods                      # DuckDB 1.3 (Superset 5) reads it back as NULL
    assert [r[0] for r in con.execute("DESCRIBE marts.fact_trips").fetchall()] == ["id"]   # audit columns left out
    assert con.execute("SELECT count(*) FROM marts.dim_zone WHERE zone = 'Zone 7'").fetchone()[0] == 400
    con.close()


# --- make clean ----------------------------------------------------------------------------------------------
def test_clean_keeps_dashboards_and_the_folders_docker_mounts(settings, monkeypatch):
    monkeypatch.setattr(dagster_instance, "wipe", lambda: None)
    data = settings.data_dir
    for path in ("raw/yellow/x.parquet", "logs/pipeline.jsonl", "bi/nyc_taxi_bi.duckdb", "superset_home/superset.db",
                 "dagster_home/storage/run/compute_logs/a.out", "dagster_home/history/runs.db", "control/control.duckdb"):
        (data / path).parent.mkdir(parents=True, exist_ok=True)
        (data / path).write_text("x", encoding="utf-8")

    clean.clean(settings)

    assert (data / "superset_home" / "superset.db").exists()
    for mounted in ("logs", "bi", "dagster_home/storage"):
        assert (data / mounted).is_dir() and not any((data / mounted).iterdir())
    assert sorted(p.name for p in data.iterdir()) == ["bi", "dagster_home", "logs", "superset_home"]
    assert [p.name for p in (data / "dagster_home").iterdir()] == ["storage"]
