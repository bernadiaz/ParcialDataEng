"""Idempotency: ingestion (mocked HTTP and mocked Airbyte + S3), quality partitions and the warehouse load."""
from __future__ import annotations

import io

import boto3
import httpx
import pytest
from moto import mock_aws

from src import calidad, ingesta_airbyte, load_snowflake
from src.config import Month, Settings
from src.ingesta_airbyte import IngestionError, Ingestor, IngestionLog
from tests.conftest import JAN_2025, ZONES_CSV, trip, write_tlc_parquet


@pytest.fixture
def parquet_bytes(tmp_path):
    return write_tlc_parquet(tmp_path / "src.parquet", [trip(), trip(trip_distance=1.5)]).read_bytes()


def _log_rows(settings, dataset="yellow"):
    from src.config import control_db

    with control_db(settings) as con:
        return con.execute(
            "SELECT action, status, attempts, sha256 FROM ingestion_log WHERE dataset = ? ORDER BY logged_at", [dataset]
        ).fetchall()


# --- direct mode (HTTP mocked) --------------------------------------------------------------------
def test_direct_ingestion_twice_downloads_once(settings, parquet_bytes):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        body = ZONES_CSV.encode() if request.url.path.endswith(".csv") else parquet_bytes
        return httpx.Response(200, content=body)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    for _ in range(2):
        ingestor = Ingestor(settings, http=http, sleep=lambda s: None)
        ingestor.zones()
        ingestor.yellow(JAN_2025)

    yellow_calls = [c for c in calls if "yellow_tripdata_2025-01" in c]
    assert len(yellow_calls) == 1                                # second run: hash matches, no download
    log = _log_rows(settings)
    assert [r[0] for r in log] == ["downloaded", "skipped"]
    assert log[0][3] == log[1][3]                                # same SHA-256
    assert list(settings.raw_month_dir(JAN_2025).iterdir()) == [
        settings.raw_month_dir(JAN_2025) / "yellow_tripdata_2025-01.parquet"
    ]


def test_direct_ingestion_downloads_again_when_the_mirror_changes(settings, parquet_bytes):
    calls: list[str] = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, content=parquet_bytes)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    Ingestor(settings, http=http, sleep=lambda s: None).yellow(JAN_2025)
    (settings.raw_month_dir(JAN_2025) / "yellow_tripdata_2025-01.parquet").write_bytes(b"corrupted")
    Ingestor(settings, http=http, sleep=lambda s: None).yellow(JAN_2025)
    assert len(calls) == 2


def test_network_failure_retries_three_times_with_growing_waits_then_fails(settings):
    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    waits: list[float] = []
    ingestor = Ingestor(settings, http=httpx.Client(transport=httpx.MockTransport(handler)), sleep=waits.append)
    with pytest.raises(IngestionError) as error:
        ingestor.yellow(JAN_2025)
    assert waits == [1, 2, 4]
    assert error.value.attempts == 4
    assert _log_rows(settings)[-1][:3] == ("failed", "error", 4)


def test_missing_month_fails_without_retries(settings):
    waits: list[float] = []
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(IngestionError, match="404"):
        Ingestor(settings, http=http, sleep=waits.append).yellow(Month(2030, 1))
    assert waits == []


def test_ingestion_cli_exits_non_zero_after_retries(settings, monkeypatch):
    def handler(request):
        raise httpx.ConnectError("network down", request=request)

    real_client = httpx.Client
    monkeypatch.setattr(ingesta_airbyte.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(ingesta_airbyte.time, "sleep", lambda s: None)
    assert ingesta_airbyte.main(["--mes", "2025-01"]) == 1


# --- Airbyte mode (Airbyte API and S3 mocked) ---------------------------------------------------------
class FakeAirbyte:
    """Behaves like the Airbyte sync: writes the configured month to the configured S3 path."""

    def __init__(self, s3_client, payloads: dict[str, bytes]):
        self.s3, self.payloads, self.syncs = s3_client, payloads, 0
        self.source: dict = {}
        self.destination: dict = {}
        self.resources: dict = {}

    def set_connection_resources(self, connection_id, resources):
        self.resources[connection_id] = resources

    def update_source(self, source_id, configuration):
        self.source = configuration

    def update_destination(self, destination_id, configuration):
        self.destination = configuration

    def run_sync(self, connection_id, **kwargs):
        self.syncs += 1
        dataset = self.source["dataset_name"]
        extension = ".csv" if self.source["format"] == "csv" else ".parquet"
        key = f"{self.destination['s3_bucket_path']}/{dataset}/part_{self.syncs}{extension}"
        self.s3.put_object(Bucket=self.destination["s3_bucket_name"], Key=key, Body=self.payloads[dataset])
        return {"jobId": 100 + self.syncs, "status": "succeeded"}


@mock_aws
def test_airbyte_ingestion_twice_syncs_once(tmp_path, monkeypatch, parquet_bytes):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name, value in {
        "DATA_DIR": str(tmp_path / "data"), "INGEST_MODE": "airbyte", "S3_BUCKET": "nyc-taxi-test",
        "AWS_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
        "S3_RAW_PREFIX": "raw", "AIRBYTE_S3_ACCESS_KEY_ID": "testing", "AIRBYTE_S3_SECRET_ACCESS_KEY": "testing",
    }.items():
        monkeypatch.setenv(name, value)
    for dataset in ("YELLOW", "ZONES"):
        for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
            monkeypatch.setenv(f"AIRBYTE_{dataset}_{kind}_ID", f"{dataset.lower()}-{kind.lower()}")
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", tmp_path / "missing.json")
    settings = Settings.from_env()
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    airbyte = FakeAirbyte(client, {"yellow_tripdata": parquet_bytes, "taxi_zone_lookup": ZONES_CSV.encode()})
    s3 = ingesta_airbyte.S3Store(settings, client=client)

    for _ in range(2):
        ingestor = Ingestor(settings, s3=s3, airbyte=airbyte, sleep=lambda s: None)
        ingestor.zones()
        ingestor.yellow(JAN_2025)

    assert airbyte.syncs == 2                                   # one per dataset, none on the second run
    assert airbyte.destination["s3_bucket_path"] == "raw/yellow/year=2025/month=01"
    assert airbyte.resources["yellow-connection"]["memory_limit"] == "7Gi"   # pod limit from the versioned YAML
    keys = [o["Key"] for o in client.list_objects_v2(Bucket="nyc-taxi-test")["Contents"]]
    assert "raw/yellow/year=2025/month=01/yellow_tripdata/part_2.parquet" in keys
    log = _log_rows(settings)
    assert [r[0] for r in log] == ["synced", "skipped"]
    mirrored = settings.raw_month_dir(JAN_2025) / "yellow_tripdata" / "part_2.parquet"
    assert mirrored.read_bytes() == parquet_bytes


@mock_aws
def test_switching_from_local_to_airbyte_lands_the_month_in_s3(tmp_path, monkeypatch, parquet_bytes):
    """A month ingested locally (direct, no S3) must not be skipped once S3/Airbyte are configured."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    base = {"DATA_DIR": str(tmp_path / "data"), "AWS_REGION": "us-east-1", "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing", "S3_RAW_PREFIX": "raw", "AIRBYTE_S3_ACCESS_KEY_ID": "testing",
            "AIRBYTE_S3_SECRET_ACCESS_KEY": "testing"}
    for name, value in (base | {"INGEST_MODE": "direct", "S3_BUCKET": ""}).items():
        monkeypatch.setenv(name, value)
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=parquet_bytes)))
    Ingestor(Settings.from_env(), http=http, sleep=lambda s: None).yellow(JAN_2025)

    for name, value in (base | {"INGEST_MODE": "airbyte", "S3_BUCKET": "nyc-taxi-test"}).items():
        monkeypatch.setenv(name, value)
    for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
        monkeypatch.setenv(f"AIRBYTE_YELLOW_{kind}_ID", f"yellow-{kind.lower()}")
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", tmp_path / "missing.json")
    settings = Settings.from_env()
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    airbyte = FakeAirbyte(client, {"yellow_tripdata": parquet_bytes})
    Ingestor(settings, s3=ingesta_airbyte.S3Store(settings, client=client), airbyte=airbyte, sleep=lambda s: None).yellow(JAN_2025)

    assert airbyte.syncs == 1
    assert [r[0] for r in _log_rows(settings)] == ["downloaded", "synced"]


@mock_aws
def test_hybrid_mode_uses_airbyte_for_zones_and_streams_months_to_s3(tmp_path, monkeypatch, parquet_bytes):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for name, value in {
        "DATA_DIR": str(tmp_path / "data"), "INGEST_MODE": "hybrid", "S3_BUCKET": "nyc-taxi-test", "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "S3_RAW_PREFIX": "raw",
        "AIRBYTE_S3_ACCESS_KEY_ID": "testing", "AIRBYTE_S3_SECRET_ACCESS_KEY": "testing",
    }.items():
        monkeypatch.setenv(name, value)
    for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
        monkeypatch.setenv(f"AIRBYTE_ZONES_{kind}_ID", f"zones-{kind.lower()}")
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", tmp_path / "missing.json")
    settings = Settings.from_env()
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="nyc-taxi-test")
    airbyte = FakeAirbyte(client, {"taxi_zone_lookup": ZONES_CSV.encode()})
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=parquet_bytes)))
    ingestor = Ingestor(settings, http=http, s3=ingesta_airbyte.S3Store(settings, client=client), airbyte=airbyte,
                        sleep=lambda s: None)

    ingestor.zones()
    ingestor.yellow(JAN_2025)

    assert airbyte.syncs == 1                                            # only the zones went through Airbyte
    key = "raw/yellow/year=2025/month=01/yellow_tripdata_2025-01.parquet"
    assert client.get_object(Bucket="nyc-taxi-test", Key=key)["Body"].read() == parquet_bytes   # unmodified
    with __import__("src.config", fromlist=["control_db"]).control_db(settings) as con:
        modes = dict(con.execute("SELECT dataset, mode FROM ingestion_log").fetchall())
    assert modes == {"zones": "airbyte", "yellow": "direct"}


class FakeAirbyteAPI:
    """Airbyte API double for setup: objects by name; the first connection create times out after
    the server already created it (what happens while Airbyte discovers a large source)."""

    def __init__(self, existing: dict[str, dict[str, str]]):
        self.objects = existing
        self.creates: list[tuple[str, str]] = []
        self.timeouts_left = 1

    def find(self, kind, name, workspace_id):
        return self.objects.get(kind, {}).get(name)

    def create(self, kind, body, timeout=None):
        object_id = f"{kind}-{len(self.creates)}"
        self.objects.setdefault(kind, {})[body["name"]] = object_id
        self.creates.append((kind, body["name"]))
        if kind == "connections" and self.timeouts_left:
            self.timeouts_left -= 1
            raise ingesta_airbyte.RetryableError("did not answer in time")
        return object_id


def test_airbyte_setup_reuses_existing_objects_and_survives_a_timeout(tmp_path, monkeypatch):
    state = tmp_path / "ids.json"
    monkeypatch.setattr(ingesta_airbyte, "STATE_FILE", state)
    for name, value in {"AIRBYTE_WORKSPACE_ID": "ws", "S3_BUCKET": "b", "AWS_REGION": "us-east-1", "S3_RAW_PREFIX": "raw",
                        "AIRBYTE_S3_ACCESS_KEY_ID": "k", "AIRBYTE_S3_SECRET_ACCESS_KEY": "s"}.items():
        monkeypatch.setenv(name, value)
    for dataset in ("YELLOW", "ZONES"):
        for kind in ("SOURCE", "DESTINATION", "CONNECTION"):
            monkeypatch.delenv(f"AIRBYTE_{dataset}_{kind}_ID", raising=False)
    # what an interrupted earlier run left behind: the yellow source and destination
    api = FakeAirbyteAPI({"sources": {"tlc-yellow-tripdata": "src-old"}, "destinations": {"s3-raw-yellow": "dst-old"}})
    waits: list[float] = []

    ids = ingesta_airbyte.setup_airbyte(api, JAN_2025, sleep=waits.append)

    assert ids["yellow"]["source_id"] == "src-old" and ids["yellow"]["destination_id"] == "dst-old"
    assert ids["yellow"]["connection_id"] == "connections-0"           # created once, found after the timeout
    assert [c for c in api.creates if c[0] == "connections"] == [
        ("connections", "nyc-taxi-yellow-monthly"), ("connections", "nyc-taxi-zones")]
    assert waits == [ingesta_airbyte.DISCOVERY_POLL_SECONDS]            # waited for it instead of re-posting
    assert ingesta_airbyte.json.loads(state.read_text())["zones"]["connection_id"]
    assert ingesta_airbyte.setup_airbyte(api, JAN_2025, sleep=waits.append) == ids   # second run: nothing new
    assert len(api.creates) == 4


# --- downstream steps --------------------------------------------------------------------------------
def test_quality_rerun_replaces_only_its_partition(settings, zones_file):
    feb = Month(2025, 2)
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip(), trip(trip_distance=0)])
    from datetime import datetime

    write_tlc_parquet(
        settings.raw_month_dir(feb) / "f.parquet",
        [trip(tpep_pickup_datetime=datetime(2025, 2, 3, 9), tpep_dropoff_datetime=datetime(2025, 2, 3, 9, 30))],
    )
    calidad.run_month(settings, feb)
    feb_bytes = (settings.curated_month_dir(feb) / "part-0.parquet").read_bytes()
    first = calidad.run_month(settings, JAN_2025)
    second = calidad.run_month(settings, JAN_2025)

    assert (first.rows_accepted, first.rows_quarantined) == (second.rows_accepted, second.rows_quarantined) == (1, 1)
    assert [p.name for p in settings.curated_month_dir(JAN_2025).iterdir()] == ["part-0.parquet"]
    assert (settings.curated_month_dir(feb) / "part-0.parquet").read_bytes() == feb_bytes


def test_warehouse_reload_of_a_month_does_not_duplicate_rows(settings, zones_file):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip(), trip(trip_distance=2.0)])
    calidad.run_month(settings, JAN_2025)
    first = load_snowflake.load_months(settings, [JAN_2025])
    second = load_snowflake.load_months(settings, [JAN_2025])
    trips_first = next(r for r in first if r.mes == "2025-01")
    trips_second = next(r for r in second if r.mes == "2025-01")
    assert (trips_first.rows_deleted, trips_first.rows_loaded) == (0, 2)
    assert (trips_second.rows_deleted, trips_second.rows_loaded) == (2, 2)


def test_a_month_not_published_yet_fails_at_once(settings):
    """The TLC CDN answers 403 (not 404) for a file that does not exist yet."""
    waits: list[float] = []
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    with pytest.raises(IngestionError, match="has not published"):
        Ingestor(settings, http=http, sleep=waits.append).yellow(Month(2030, 1))
    assert waits == []
    assert ingesta_airbyte.month_published(Month(2030, 1), http=http) is False
    ok = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    assert ingesta_airbyte.month_published(Month(2025, 1), http=ok) is True


def test_a_refused_request_is_not_mistaken_for_a_missing_month(settings):
    """CloudFront answers its own HTML 403 page when it throttles an address: that says nothing about the file."""
    page = httpx.Response(403, headers={"content-type": "text/html"}, text="<H1>403 ERROR</H1> could not be satisfied")
    http = httpx.Client(transport=httpx.MockTransport(lambda request: page))
    assert ingesta_airbyte.month_published(Month(2025, 4), http=http) is None
    with pytest.raises(IngestionError, match="refused the request"):
        Ingestor(settings, http=http, sleep=lambda s: None).yellow(Month(2025, 4))
    missing = httpx.Response(403, headers={"content-type": "application/xml"}, text="<Error><Code>AccessDenied</Code></Error>")
    http = httpx.Client(transport=httpx.MockTransport(lambda request: missing))
    assert ingesta_airbyte.month_published(Month(2030, 1), http=http) is False
