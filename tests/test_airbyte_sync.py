"""Airbyte syncs never hang the pipeline: stuck jobs are cancelled, failures fall back to the direct path,
and hybrid mode only sets up the zone connection (the yellow File-source connection cannot finish)."""
from __future__ import annotations

import json

import boto3
import httpx
import pytest
from moto import mock_aws

from src import ingesta_airbyte
from src.config import Settings, control_db
from src.ingesta_airbyte import AirbyteClient, IngestionError, Ingestor
from tests.conftest import JAN_2025, ZONES_CSV
from tests.test_idempotencia import FakeAirbyteAPI


class ScriptedAPI(AirbyteClient):
    """AirbyteClient whose API answers come from a script of job states (no HTTP)."""

    def __init__(self, statuses: list[str], running: tuple = ()):
        self.statuses, self.running = list(statuses), list(running)
        self.cancelled: list[int] = []
        self.started = 0

    def request(self, method, path, body=None, timeout=None):
        if method == "GET" and path.startswith("/jobs?"):
            return {"data": [{"jobId": j, "status": "running"} for j in self.running if j not in self.cancelled]}
        if method == "POST" and path == "/jobs":
            self.started += 1
            return {"jobId": 100, "status": self.statuses.pop(0)}
        if method == "GET" and path.startswith("/jobs/"):
            return {"jobId": 100, "status": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]}
        if method == "DELETE" and path.startswith("/jobs/"):
            self.cancelled.append(int(path.rsplit("/", 1)[1]))
            return {}
        raise AssertionError(f"unexpected call {method} {path}")


def test_a_sync_stuck_in_syncing_is_cancelled_after_the_timeout():
    api = ScriptedAPI(["running"] * 100)
    with pytest.raises(IngestionError, match="cancelled"):
        api.run_sync("conn", poll_seconds=10, timeout_seconds=60, sleep=lambda s: None)
    assert api.cancelled == [100]


def test_a_failed_sync_is_not_started_again():
    api = ScriptedAPI(["running", "failed"])
    with pytest.raises(IngestionError, match="ended failed"):
        api.run_sync("conn", poll_seconds=10, timeout_seconds=600, sleep=lambda s: None)
    assert api.started == 1                       # Airbyte already retried its attempts


def test_a_job_left_running_by_hand_is_cancelled_before_the_next_sync():
    api = ScriptedAPI(["running", "succeeded"], running=(7,))
    job = api.run_sync("conn", poll_seconds=10, timeout_seconds=30, sleep=lambda s: None)
    assert api.cancelled == [7] and job["status"] == "succeeded"


def test_hybrid_mode_only_sets_up_the_zone_connection(tmp_path, monkeypatch):
    assert ingesta_airbyte.airbyte_datasets("hybrid") == ["zones"]
    assert ingesta_airbyte.airbyte_datasets("airbyte") == ["zones", "yellow"]
    assert ingesta_airbyte.airbyte_datasets("direct") == []
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", tmp_path / "ids.json")
    for name, value in {"AIRBYTE_WORKSPACE_ID": "ws", "S3_BUCKET": "b", "AWS_REGION": "us-east-1",
                        "S3_RAW_PREFIX": "raw", "AIRBYTE_S3_ACCESS_KEY_ID": "k", "AIRBYTE_S3_SECRET_ACCESS_KEY": "s"}.items():
        monkeypatch.setenv(name, value)
    api = FakeAirbyteAPI({})

    ids = ingesta_airbyte.setup_airbyte(api, JAN_2025, sleep=lambda s: None, datasets=["zones"])

    assert ids["zones"]["connection_id"]
    assert not any("yellow" in name for _, name in api.creates)   # no yellow source, destination or connection


class FailingAirbyte:
    def update_source(self, *a):
        pass

    def update_destination(self, *a):
        pass

    def set_connection_resources(self, *a):
        pass

    def run_sync(self, connection_id, **kwargs):
        raise IngestionError("Airbyte job 9 was still running after 30 min: cancelled (AIRBYTE_SYNC_TIMEOUT_MINUTES)")


@pytest.fixture
def hybrid(tmp_path, monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name, value in {"DATA_DIR": str(tmp_path / "data"), "INGEST_MODE": "hybrid", "WAREHOUSE": "snowflake",
                        "S3_BUCKET": "nyc-taxi-test", "AWS_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing",
                        "AWS_SECRET_ACCESS_KEY": "testing", "S3_RAW_PREFIX": "raw",
                        "AIRBYTE_S3_ACCESS_KEY_ID": "testing", "AIRBYTE_S3_SECRET_ACCESS_KEY": "testing"}.items():
        monkeypatch.setenv(name, value)
    for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
        monkeypatch.setenv(f"AIRBYTE_ZONES_{kind}_ID", f"zones-{kind.lower()}")
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", tmp_path / "missing.json")
    return Settings.from_env()


@mock_aws
def test_a_failed_airbyte_sync_falls_back_to_the_direct_path(hybrid, monkeypatch):
    monkeypatch.setenv("AIRBYTE_FALLBACK", "direct")
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=ZONES_CSV.encode())))

    Ingestor(hybrid, http=http, s3=ingesta_airbyte.S3Store(hybrid, client=client), airbyte=FailingAirbyte(),
             sleep=lambda s: None).zones()

    assert client.get_object(Bucket="nyc-taxi-test", Key="raw/zones/taxi_zone_lookup.csv")["Body"].read() == ZONES_CSV.encode()
    with control_db(hybrid) as con:
        log = con.execute("SELECT mode, action, status, error FROM ingestion_log ORDER BY logged_at").fetchall()
    assert [r[:3] for r in log] == [("airbyte", "failed", "error"), ("direct", "downloaded", "ok")]
    assert "cancelled" in log[0][3]                         # the stuck sync is the recorded reason


@mock_aws
def test_the_fallback_can_be_disabled(hybrid, monkeypatch):
    monkeypatch.setenv("AIRBYTE_FALLBACK", "fail")
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    with pytest.raises(IngestionError, match="cancelled"):
        Ingestor(hybrid, s3=ingesta_airbyte.S3Store(hybrid, client=client), airbyte=FailingAirbyte(),
                 sleep=lambda s: None).zones()


class PruneAPI(AirbyteClient):
    def __init__(self):
        self.deleted: list[str] = []

    def find(self, kind, name, workspace_id):
        return None

    def request(self, method, path, body=None, timeout=None):
        if method == "GET" and path.startswith("/jobs?"):
            return {"data": []}
        if method == "DELETE":
            self.deleted.append(path)
            return {}
        raise AssertionError(path)


def test_prune_deletes_only_the_objects_the_mode_does_not_use(tmp_path, monkeypatch):
    state = tmp_path / "ids.json"
    state.write_text(json.dumps({
        "yellow": {"source_id": "ys", "destination_id": "yd", "connection_id": "yc"},
        "zones": {"source_id": "zs", "destination_id": "zd", "connection_id": "zc"},
    }), encoding="utf-8")
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", state)
    for dataset in ("YELLOW", "ZONES"):
        for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
            monkeypatch.delenv(f"AIRBYTE_{dataset}_{kind}_ID", raising=False)
    api = PruneAPI()

    ingesta_airbyte.prune_unused(api, "hybrid")

    assert api.deleted == ["/connections/yc", "/sources/ys", "/destinations/yd"]
    assert set(json.loads(state.read_text(encoding="utf-8"))) == {"zones"}
