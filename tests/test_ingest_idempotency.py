"""Idempotencia de ingesta: segunda corrida no re-descarga si el hash coincide."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src import ingesta_airbyte as ing
from src.object_store import FsObjectStore


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        env="dev",
        mes="2025-03",
        data_dir=tmp_path,
        s3_endpoint_url="http://localhost:9000",
        s3_access_key_id="minioadmin",
        s3_secret_access_key="minioadmin",
        s3_bucket="nyc-taxi-test",
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


def test_parse_mes_and_comparison():
    ref = ing.parse_mes("2025-03")
    assert ref.year == 2025 and ref.month == 3
    assert ing.comparison_month(ref).label == "2024-03"
    with pytest.raises(ValueError):
        ing.parse_mes("2025/03")


def test_ingest_file_skips_when_local_and_store_hash_match(tmp_path: Path):
    settings = _settings(tmp_path)
    local = tmp_path / "raw" / "zones" / "taxi_zone_lookup.csv"
    local.parent.mkdir(parents=True)
    local.write_text("LocationID,Borough\n1,EWR\n", encoding="utf-8")
    digest = ing.sha256_file(local)

    store = MagicMock()
    store.exists.return_value = True
    store.get_sha256.return_value = digest

    with patch.object(ing, "download_with_retries") as dl:
        status = ing.ingest_file(
            settings=settings,
            store=store,
            backend="fs",
            archivo="taxi_zone_lookup.csv",
            url="https://example.com/zones.csv",
            local_path=local,
            store_key="raw/zones/taxi_zone_lookup.csv",
            content_type="text/csv",
            count_fn=ing.csv_row_count,
        )

    assert status == "skipped"
    dl.assert_not_called()
    store.put_file.assert_not_called()

    log = (tmp_path / "control" / "ingestion_log.csv").read_text(encoding="utf-8")
    assert "skipped" in log
    assert digest in log


def test_ingest_file_downloads_when_missing(tmp_path: Path):
    settings = _settings(tmp_path)
    local = tmp_path / "raw" / "zones" / "taxi_zone_lookup.csv"
    content = b"LocationID,Borough\n1,EWR\n"
    store = FsObjectStore(root=tmp_path / "object_store")

    def fake_download(url, dest, max_retries=3):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return hashlib.sha256(content).hexdigest(), len(content)

    with patch.object(ing, "download_with_retries", side_effect=fake_download) as dl:
        status = ing.ingest_file(
            settings=settings,
            store=store,
            backend="fs",
            archivo="taxi_zone_lookup.csv",
            url="https://example.com/zones.csv",
            local_path=local,
            store_key="raw/zones/taxi_zone_lookup.csv",
            content_type="text/csv",
            count_fn=ing.csv_row_count,
        )

    assert status == "ok"
    assert local.exists()
    assert store.exists("raw/zones/taxi_zone_lookup.csv")
    assert store.get_sha256("raw/zones/taxi_zone_lookup.csv") == hashlib.sha256(content).hexdigest()
    dl.assert_called_once()


def test_second_run_skips_with_fs_store(tmp_path: Path):
    """Flujo real de idempotencia con FsObjectStore (sin red)."""
    settings = _settings(tmp_path)
    store = FsObjectStore(root=tmp_path / "object_store")
    local = tmp_path / "raw" / "zones" / "taxi_zone_lookup.csv"
    content = b"LocationID,Borough\n1,EWR\n"

    def fake_download(url, dest, max_retries=3):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return hashlib.sha256(content).hexdigest(), len(content)

    kwargs = dict(
        settings=settings,
        store=store,
        backend="fs",
        archivo="taxi_zone_lookup.csv",
        url="https://example.com/zones.csv",
        local_path=local,
        store_key="raw/zones/taxi_zone_lookup.csv",
        content_type="text/csv",
        count_fn=ing.csv_row_count,
    )

    with patch.object(ing, "download_with_retries", side_effect=fake_download) as dl:
        assert ing.ingest_file(**kwargs) == "ok"
        assert ing.ingest_file(**kwargs) == "skipped"
        assert dl.call_count == 1
