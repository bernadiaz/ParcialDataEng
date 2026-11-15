"""Part 1 - ingestion (Airbyte -> S3), with verification and ingestion_log.

INGEST_MODE=airbyte (plan default)
    Airbyte's File source reads the TLC file over HTTPS, and its S3 destination lands it under
    s3://<bucket>/raw/yellow/year=YYYY/month=MM/ (zones under raw/zones/). The connection is
    versioned in airbyte/connections/*.yaml, and this wrapper sets the month on it before every
    sync. A failed job is retried 3 times, waiting 1 s, 2 s and 4 s. After the sync the wrapper
    removes objects left by older syncs of that month, mirrors the month to data/raw computing
    SHA-256, checks the Parquet row count against the job and logs every file.

INGEST_MODE=direct (fallback, no Airbyte needed)
    Downloads the same files from the TLC CDN with the same retries and log, and uploads them
    unmodified to the same S3 path when S3_BUCKET is set.

Idempotency: a month (and the zone lookup) is skipped when its last successful log entries still
match the local mirror (SHA-256) and S3 (size + ETag). Nothing is synced or downloaded again.
After the last retry fails, the error is logged and the process exits with code 1.

The Airbyte source, destination and connection of each dataset are created automatically the first
time they are needed (idempotent: reused by name, never duplicated). `--setup` only does it ahead
of time.

    python -m src.ingesta_airbyte --mes 2025-01 --mes 2024-01
    python -m src.ingesta_airbyte --setup                  # optional: create the Airbyte objects now
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import duckdb
import httpx
import yaml

from src.config import (
    ROOT,
    RUN_ID,
    YELLOW_URL_TEMPLATE,
    ZONES_URL,
    Month,
    Settings,
    control_db,
    get_logger,
    track_step,
)
from src.observability import push

log = get_logger("ingesta")

AIRBYTE_DIR = ROOT / "airbyte"
CONNECTION_FILES = {
    "yellow": AIRBYTE_DIR / "connections" / "yellow_tripdata.yaml",
    "zones": AIRBYTE_DIR / "connections" / "taxi_zone_lookup.yaml",
}
STATE_FILE = AIRBYTE_DIR / "state" / "ids.json"
RETRY_DELAYS = (1, 2, 4)  # seconds between attempts: 1 try + 3 retries
CHUNK = 8 * 1024 * 1024
STALE_TOLERANCE = timedelta(minutes=2)  # clock skew allowed when spotting leftovers of older syncs
ZONES_MES = "static"


class IngestionError(RuntimeError):
    """Ends the ingestion with exit code 1 (after logging the error)."""

    def __init__(self, message: str, attempts: int = 1):
        super().__init__(message)
        self.attempts = attempts


class RetryableError(RuntimeError):
    """Network failures, HTTP 429/5xx and failed Airbyte jobs."""


def with_retries(action: Callable[[], Any], *, what: str, sleep: Callable[[float], None] = time.sleep) -> tuple[Any, int]:
    """Runs action(); on RetryableError waits 1 s, 2 s, 4 s and tries again. Returns (result, attempts)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return action(), attempt
        except RetryableError as exc:
            if attempt > len(RETRY_DELAYS):
                raise IngestionError(f"{what} failed after {attempt} attempts: {exc}", attempts=attempt) from exc
            delay = RETRY_DELAYS[attempt - 1]
            log.warning("%s failed (attempt %d/%d): %s. Retrying in %ss", what, attempt, len(RETRY_DELAYS) + 1, exc, delay)
            sleep(delay)
        except IngestionError as exc:
            exc.attempts = attempt
            raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_rows(path: Path) -> int:
    """Parquet: footer metadata (no full read). CSV: data rows."""
    reader = "read_parquet" if path.suffix == ".parquet" else "read_csv"
    with duckdb.connect() as con:
        return con.execute(f"SELECT count(*) FROM {reader}('{path.as_posix()}')").fetchone()[0]


# --- ingestion_log ---------------------------------------------------------------------------
class IngestionLog:
    """Control table ingestion_log: file, URL, bytes, SHA-256, rows, timestamp and status."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def push_metrics(dataset: str, mes: str, entries: list[dict[str, Any]], action: str, attempts: int, ok: bool) -> None:
        labels = {"dataset": dataset}
        push(f"ingest-{dataset}", mes, [
            ("nyc_taxi_ingested_bytes", "Bytes of the landed files", labels, float(sum(e.get("bytes") or 0 for e in entries))),
            ("nyc_taxi_ingested_rows", "Rows of the landed files (Parquet metadata)", labels,
             float(sum(e.get("row_count") or 0 for e in entries))),
            ("nyc_taxi_ingestion_skipped", "1 if the files were already current (no download)", labels, 1.0 if action == "skipped" else 0.0),
            ("nyc_taxi_ingestion_attempts", "Attempts used by the last ingestion", labels, float(attempts)),
            ("nyc_taxi_ingestion_success", "1 if the last ingestion succeeded", labels, 1.0 if ok else 0.0),
        ])

    def append(self, **entry: Any) -> None:
        row = {
            "run_id": RUN_ID, "dataset": None, "mes": None, "file": None, "url": None, "s3_uri": None,
            "bytes": None, "sha256": None, "row_count": None, "etag": None, "mode": None, "action": None,
            "airbyte_job_id": None, "attempts": None, "status": None, "error": None,
        } | entry
        with control_db(self.settings) as con:
            con.execute(
                "INSERT INTO ingestion_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())",
                [row[k] for k in (
                    "run_id", "dataset", "mes", "file", "url", "s3_uri", "bytes", "sha256", "row_count",
                    "etag", "mode", "action", "airbyte_job_id", "attempts", "status", "error",
                )],
            )

    def last_ok(self, dataset: str, mes: str) -> list[dict[str, Any]]:
        """Entries of the most recent successful run for that dataset and month."""
        with control_db(self.settings) as con:
            cursor = con.execute(
                """SELECT * FROM ingestion_log
                   WHERE dataset = ? AND mes = ? AND status = 'ok' AND run_id = (
                       SELECT run_id FROM ingestion_log WHERE dataset = ? AND mes = ? AND status = 'ok'
                       ORDER BY logged_at DESC LIMIT 1)""",
                [dataset, mes, dataset, mes],
            )
            names = [d[0] for d in cursor.description]
            return [dict(zip(names, row)) for row in cursor.fetchall()]


# --- S3 ----------------------------------------------------------------------------------------
class S3Store:
    """Thin boto3 wrapper. Credentials come from the AWS profile (AWS Toolkit / ~/.aws), never code."""

    def __init__(self, settings: Settings, client: Any | None = None):
        if client is None:
            import boto3

            session = boto3.session.Session(profile_name=settings.aws_profile or None, region_name=settings.aws_region)
            client = session.client("s3")
        self.client = client
        self.bucket = settings.s3_bucket

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def list(self, prefix: str) -> list[dict[str, Any]]:
        objects = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith("/"):
                    continue
                objects.append({
                    "key": obj["Key"], "size": obj["Size"], "etag": obj["ETag"].strip('"'),
                    "last_modified": obj["LastModified"],
                })
        return objects

    def download(self, key: str, dest: Path) -> tuple[int, str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        digest, size = hashlib.sha256(), 0
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        with tmp.open("wb") as fh:
            for chunk in body.iter_chunks(CHUNK):
                fh.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        os.replace(tmp, dest)
        return size, digest.hexdigest()

    def upload(self, path: Path, key: str) -> dict[str, Any]:
        self.client.upload_file(str(path), self.bucket, key)
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        return {"key": key, "size": head["ContentLength"], "etag": head["ETag"].strip('"')}

    def delete(self, keys: list[str]) -> None:
        for start in range(0, len(keys), 1000):
            batch = [{"Key": k} for k in keys[start:start + 1000]]
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})


# --- Airbyte public API ---------------------------------------------------------------------
_PLACEHOLDER = re.compile(r"\{(env\.[A-Z0-9_]+|year|month|mes)\}")


def render(value: Any, month: Month | None) -> Any:
    """Fills {year}, {month}, {mes} and {env.NAME} in a connection template. Airbyte's own
    ${STREAM_NAME}-style variables are left untouched."""
    if isinstance(value, dict):
        return {k: render(v, month) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, month) for v in value]
    if not isinstance(value, str):
        return value

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key.startswith("env."):
            env_value = os.environ.get(key[4:], "").strip()
            if not env_value:
                raise IngestionError(f"{key[4:]} is not set: add it to .env")
            return env_value
        if month is None:
            raise IngestionError(f"placeholder {{{key}}} needs a month")
        return {"year": f"{month.year:04d}", "month": f"{month.month:02d}", "mes": month.label}[key]

    return _PLACEHOLDER.sub(substitute, value)


def load_connection(dataset: str) -> dict[str, Any]:
    return yaml.safe_load(CONNECTION_FILES[dataset].read_text(encoding="utf-8"))


def load_ids() -> dict[str, dict[str, str]]:
    """Airbyte object ids: airbyte/state/ids.json (written by --setup), overridable from .env
    with AIRBYTE_<DATASET>_<SOURCE|DESTINATION|CONNECTION>_ID."""
    ids: dict[str, dict[str, str]] = {"yellow": {}, "zones": {}}
    if STATE_FILE.exists():
        ids.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    for dataset in ids:
        for kind in ("source", "destination", "connection"):
            env_value = os.environ.get(f"AIRBYTE_{dataset.upper()}_{kind.upper()}_ID", "").strip()
            if env_value:
                ids[dataset][f"{kind}_id"] = env_value
    return ids


class AirbyteClient:
    """Airbyte public API (abctl local install: http://localhost:8000/api/public/v1)."""

    # "incomplete" is not final: the attempt failed and Airbyte will retry it by itself.
    TERMINAL = {"succeeded", "failed", "cancelled"}
    BUSY = {"pending", "running", "incomplete"}

    def __init__(self, base_url: str, client_id: str, client_secret: str, *, http: httpx.Client | None = None):
        if not (base_url and client_id and client_secret):
            raise IngestionError("AIRBYTE_API_URL, AIRBYTE_CLIENT_ID and AIRBYTE_CLIENT_SECRET must be set in .env")
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http or httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self._token: str | None = None

    def _authenticate(self) -> str:
        response = self.http.post(
            f"{self.base_url}/applications/token",
            json={"client_id": self.client_id, "client_secret": self.client_secret, "grant-type": "client_credentials"},
        )
        if response.status_code >= 400:
            raise IngestionError(f"Airbyte authentication failed: HTTP {response.status_code} {response.text[:200]}")
        return response.json()["access_token"]

    def request(self, method: str, path: str, body: dict[str, Any] | None = None,
                timeout: float | None = None) -> dict[str, Any]:
        for retry_auth in (True, False):
            self._token = self._token or self._authenticate()
            try:
                response = self.http.request(
                    method, f"{self.base_url}{path}", json=body, headers={"Authorization": f"Bearer {self._token}"},
                    **({"timeout": httpx.Timeout(timeout, connect=10.0)} if timeout else {}),
                )
            except httpx.TimeoutException as exc:
                raise RetryableError(f"Airbyte API {method} {path} did not answer in time: {exc}") from exc
            except httpx.TransportError as exc:
                raise RetryableError(f"Airbyte API unreachable: {exc}") from exc
            if response.status_code == 401 and retry_auth:
                self._token = None
                continue
            if response.status_code == 429 or response.status_code >= 500:
                raise RetryableError(f"Airbyte API {method} {path}: HTTP {response.status_code}")
            if response.status_code >= 400:
                raise IngestionError(f"Airbyte API {method} {path}: HTTP {response.status_code} {response.text[:300]}")
            return response.json() if response.content else {}
        raise IngestionError("Airbyte API: unauthorized")

    ID_KEYS = {"sources": "sourceId", "destinations": "destinationId", "connections": "connectionId"}

    def create(self, kind: str, body: dict[str, Any], timeout: float | None = None) -> str:
        return self.request("POST", f"/{kind}", body, timeout=timeout)[self.ID_KEYS[kind]]

    def find(self, kind: str, name: str, workspace_id: str) -> str | None:
        """Id of the object with that name in the workspace (setup reuses it instead of duplicating)."""
        offset = 0
        while True:
            page = self.request("GET", f"/{kind}?workspaceIds={workspace_id}&limit=100&offset={offset}")
            items = page.get("data", [])
            for item in items:
                if item.get("name") == name:
                    return item[self.ID_KEYS[kind]]
            if len(items) < 100:
                return None
            offset += 100

    def set_connection_resources(self, connection_id: str, resources: dict[str, str]) -> None:
        """Job pod resources of a connection. The public API does not expose them, so this uses the
        config API next to it (/api/v1) with the same token. Partial update: the catalog is kept."""
        config_api = self.base_url.replace("/api/public/v1", "/api/v1")
        for retry_auth in (True, False):
            self._token = self._token or self._authenticate()
            try:
                response = self.http.post(f"{config_api}/connections/update", headers={"Authorization": f"Bearer {self._token}"},
                                          json={"connectionId": connection_id, "resourceRequirements": resources})
            except httpx.TransportError as exc:
                raise RetryableError(f"Airbyte config API unreachable: {exc}") from exc
            if response.status_code == 401 and retry_auth:
                self._token = None
                continue
            if response.status_code >= 400:
                raise IngestionError(f"Airbyte config API connections/update: HTTP {response.status_code} {response.text[:300]}")
            return

    def update_source(self, source_id: str, configuration: dict[str, Any]) -> None:
        self.request("PATCH", f"/sources/{source_id}", {"configuration": configuration})

    def update_destination(self, destination_id: str, configuration: dict[str, Any]) -> None:
        self.request("PATCH", f"/destinations/{destination_id}", {"configuration": configuration})

    def wait_for_running_jobs(self, connection_id: str, *, poll_seconds: float = 15, timeout_seconds: float = 3600,
                              sleep: Callable[[float], None] = time.sleep) -> None:
        """Airbyte refuses a second job on a busy connection (HTTP 409), e.g. when it retries an
        interrupted job by itself after a restart. Wait until the connection is idle."""
        waited = 0.0
        while True:
            running = [j for j in self.request("GET", f"/jobs?connectionId={connection_id}&limit=20").get("data", [])
                       if j.get("status") in self.BUSY]
            if not running:
                return
            if waited >= timeout_seconds:
                raise RetryableError(f"connection {connection_id} still busy with job(s) {[j['jobId'] for j in running]}")
            log.info("Airbyte connection busy with job(s) %s, waiting", [j["jobId"] for j in running])
            sleep(poll_seconds)
            waited += poll_seconds

    def run_sync(self, connection_id: str, *, poll_seconds: float = 10, timeout_seconds: float = 3600,
                 sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
        self.wait_for_running_jobs(connection_id, sleep=sleep, timeout_seconds=timeout_seconds)
        job = self.request("POST", "/jobs", {"connectionId": connection_id, "jobType": "sync"})
        job_id = job["jobId"]
        log.info("Airbyte job %s started for connection %s", job_id, connection_id)
        waited = 0.0
        while job.get("status") not in self.TERMINAL:
            if waited >= timeout_seconds:
                raise RetryableError(f"Airbyte job {job_id} still {job.get('status')} after {timeout_seconds:.0f}s")
            sleep(poll_seconds)
            waited += poll_seconds
            job = self.request("GET", f"/jobs/{job_id}")
        if job["status"] != "succeeded":
            raise RetryableError(f"Airbyte job {job_id} ended {job['status']}")
        return job


# Creating a connection makes Airbyte discover the source schema, and the File source downloads
# and reads the whole file to do it (about 60 MB for a month), which can take several minutes.
# Airbyte's proxy answers HTTP 502 after 5 minutes while the server keeps working, so after a
# failed create the setup waits for the connection to appear before asking again.
DISCOVERY_TIMEOUT_SECONDS = 900
DISCOVERY_WAIT_SECONDS = 1200
DISCOVERY_POLL_SECONDS = 30


def _save_ids(ids: dict[str, dict[str, str]]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(ids, indent=2), encoding="utf-8")


def setup_airbyte(client: AirbyteClient, month: Month, sleep: Callable[[float], None] = time.sleep) -> dict[str, dict[str, str]]:
    """Makes sure the source, destination and manual connection of each dataset exist.

    Idempotent and automatic. An object that already exists with the versioned name is reused,
    never duplicated, and every id is saved as soon as it is known, so an interrupted setup simply
    continues on the next run. Timeouts and 5xx answers are retried (1 s, 2 s, 4 s), and every
    retry looks the object up first. Ingestion calls this by itself when an id is missing.
    """
    workspace = os.environ.get("AIRBYTE_WORKSPACE_ID", "").strip()
    if not workspace:
        raise IngestionError("AIRBYTE_WORKSPACE_ID is not set in .env (the UUID in the Airbyte UI URL)")
    ids = load_ids()

    def ensure(dataset: str, field: str, kind: str, name: str, body: dict[str, Any], timeout: float | None = None,
               wait_after_failure: float = 0) -> str:
        current = ids.setdefault(dataset, {})
        if current.get(field):
            return current[field]

        def find_or_create() -> str:
            existing = client.find(kind, name, workspace)
            if existing:
                return existing
            try:
                return client.create(kind, body, timeout=timeout)
            except RetryableError:
                # The server may still finish the request (schema discovery). Wait for the object
                # instead of starting another discovery that would compete with the first one.
                waited = 0.0
                while waited < wait_after_failure:
                    sleep(DISCOVERY_POLL_SECONDS)
                    waited += DISCOVERY_POLL_SECONDS
                    existing = client.find(kind, name, workspace)
                    if existing:
                        log.info("Airbyte %s %r appeared after %.0fs", kind[:-1], name, waited)
                        return existing
                raise

        current[field], _ = with_retries(find_or_create, what=f"Airbyte setup {kind[:-1]} {name!r}", sleep=sleep)
        _save_ids(ids)
        log.info("Airbyte %s %s ready: %s", kind[:-1], name, current[field])
        return current[field]

    for dataset in CONNECTION_FILES:
        spec = load_connection(dataset)
        source_id = ensure(dataset, "source_id", "sources", spec["source"]["name"], {
            "name": spec["source"]["name"], "workspaceId": workspace,
            "configuration": render(spec["source"]["configuration"], month)})
        destination_id = ensure(dataset, "destination_id", "destinations", spec["destination"]["name"], {
            "name": spec["destination"]["name"], "workspaceId": workspace,
            "configuration": render(spec["destination"]["configuration"], month)})
        log.info("Airbyte %s: creating the connection discovers the source schema (can take a few minutes)", dataset)
        ensure(dataset, "connection_id", "connections", spec["connection"]["name"], {
            "name": spec["connection"]["name"],
            "sourceId": source_id,
            "destinationId": destination_id,
            "schedule": {"scheduleType": "manual"},
            "namespaceDefinition": "destination",
            "configurations": {"streams": [{"name": spec["connection"]["stream"], "syncMode": spec["connection"]["sync_mode"]}]},
        }, timeout=DISCOVERY_TIMEOUT_SECONDS, wait_after_failure=DISCOVERY_WAIT_SECONDS)
    log.info("Airbyte setup complete: %s", STATE_FILE)
    return ids


# --- the ingestion step ------------------------------------------------------------------------
class Ingestor:
    def __init__(
        self,
        settings: Settings,
        *,
        http: httpx.Client | None = None,
        s3: S3Store | None = None,
        airbyte: AirbyteClient | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.log = IngestionLog(settings)
        self.sleep = sleep
        self.http = http or httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True)
        if s3 is None and settings.s3_bucket:
            s3 = S3Store(settings)
        self.s3 = s3
        if settings.ingest_mode in {"airbyte", "hybrid"}:
            if self.s3 is None:
                raise IngestionError(f"INGEST_MODE={settings.ingest_mode} needs S3_BUCKET (and the AWS profile) in .env")
            self.airbyte = airbyte or AirbyteClient(
                os.environ.get("AIRBYTE_API_URL", ""), os.environ.get("AIRBYTE_CLIENT_ID", ""),
                os.environ.get("AIRBYTE_CLIENT_SECRET", ""),
            )
        else:
            self.airbyte = airbyte

    def mode_for(self, dataset: str) -> str:
        """hybrid: Airbyte syncs the small zone lookup; the monthly trip files are streamed straight to S3.
        Airbyte's File source loads a whole month into pandas (about 2.5 GB for 3.5M rows), which does not
        fit next to the Airbyte platform on an 8 GB machine. The direct path keeps memory constant and
        lands the original, unmodified file."""
        if self.settings.ingest_mode == "hybrid":
            return "airbyte" if dataset == "zones" else "direct"
        return self.settings.ingest_mode

    # -- public entry points
    def zones(self) -> None:
        self._ingest("zones", None, ZONES_URL, self.settings.raw_zones_dir, "taxi_zone_lookup.csv")

    def yellow(self, month: Month) -> None:
        url = YELLOW_URL_TEMPLATE.format(mes=month.label)
        self._ingest("yellow", month, url, self.settings.raw_month_dir(month), f"yellow_tripdata_{month.label}.parquet")

    # -- shared logic
    def _ingest(self, dataset: str, month: Month | None, url: str, mirror_dir: Path, file_name: str) -> None:
        mes = month.label if month else ZONES_MES
        prefix = self.settings.s3_prefix(dataset, month)
        if self._is_current(dataset, mes, prefix):
            return
        try:
            if self.mode_for(dataset) == "airbyte":
                self._via_airbyte(dataset, month, mes, url, prefix, mirror_dir)
            else:
                self._direct(dataset, mes, url, prefix, mirror_dir, file_name)
        except IngestionError as exc:
            self.log.append(dataset=dataset, mes=mes, url=url, mode=self.mode_for(dataset), action="failed",
                            attempts=exc.attempts, status="error", error=str(exc))
            IngestionLog.push_metrics(dataset, mes, [], "failed", exc.attempts, ok=False)
            raise

    def _is_current(self, dataset: str, mes: str, prefix: str) -> bool:
        """True when the last successful ingestion still matches the mirror and S3 (no re-download)."""
        entries = self.log.last_ok(dataset, mes)
        if not entries:
            return False
        if self.s3 is not None and any(not e["s3_uri"] for e in entries):
            # e.g. an earlier local run (INGEST_MODE=direct without S3): the files never reached S3
            log.info("%s %s: ingested before but not in S3, ingesting again", dataset, mes)
            return False
        for entry in entries:
            local = self.settings.data_dir / entry["file"]
            if not local.exists() or sha256_file(local) != entry["sha256"]:
                log.info("%s %s: local mirror missing or changed, ingesting again", dataset, mes)
                return False
        if self.s3 is not None and any(e["s3_uri"] for e in entries):
            remote = {o["key"]: o for o in self.s3.list(prefix)}
            expected = {e["s3_uri"].split(f"s3://{self.s3.bucket}/", 1)[-1]: e for e in entries if e["s3_uri"]}
            if set(remote) != set(expected) or any(
                remote[k]["etag"] != e["etag"] or remote[k]["size"] != e["bytes"] for k, e in expected.items()
            ):
                log.info("%s %s: S3 objects differ from the log, ingesting again", dataset, mes)
                return False
        for entry in entries:
            self.log.append(**{k: entry[k] for k in (
                "dataset", "mes", "file", "url", "s3_uri", "bytes", "sha256", "row_count", "etag", "airbyte_job_id")},
                mode=self.mode_for(dataset), action="skipped", attempts=0, status="ok")
        IngestionLog.push_metrics(dataset, mes, entries, "skipped", 0, ok=True)
        log.info("%s %s: already ingested and hash matches, skipped (no new download)", dataset, mes)
        return True

    def _via_airbyte(self, dataset: str, month: Month | None, mes: str, url: str, prefix: str, mirror_dir: Path) -> None:
        spec = load_connection(dataset)
        ids = load_ids().get(dataset, {})
        if any(not ids.get(k) for k in ("source_id", "destination_id", "connection_id")):
            log.info("Airbyte objects for %s not set up yet: creating them automatically", dataset)
            ids = setup_airbyte(self.airbyte, month or Month(2025, 1), sleep=self.sleep).get(dataset, {})
        started = datetime.now(timezone.utc)

        def sync() -> dict[str, Any]:
            self.airbyte.update_source(ids["source_id"], render(spec["source"]["configuration"], month))
            self.airbyte.update_destination(ids["destination_id"], render(spec["destination"]["configuration"], month))
            if spec["connection"].get("resources"):
                self.airbyte.set_connection_resources(ids["connection_id"], spec["connection"]["resources"])
            return self.airbyte.run_sync(ids["connection_id"], sleep=self.sleep)

        job, attempts = with_retries(sync, what=f"Airbyte sync {dataset} {mes}", sleep=self.sleep)

        objects = self.s3.list(prefix)
        stale = [o["key"] for o in objects if o["last_modified"] < started - STALE_TOLERANCE]
        if stale:  # overwrite safety net: only objects of this month's prefix, older than this sync
            log.warning("%s %s: removing %d objects left by older syncs", dataset, mes, len(stale))
            self.s3.delete(stale)
        fresh = [o for o in objects if o["key"] not in set(stale)]
        if not fresh:
            raise IngestionError(f"Airbyte job {job.get('jobId')} succeeded but {self.s3.uri(prefix)} is empty", attempts)

        shutil.rmtree(mirror_dir, ignore_errors=True)
        entries, total_rows = [], 0
        for obj in fresh:
            local = mirror_dir / obj["key"][len(prefix):]
            size, digest = self.s3.download(obj["key"], local)
            rows = count_rows(local)
            total_rows += rows
            entries.append({"file": self.settings.relative(local), "s3_uri": self.s3.uri(obj["key"]), "bytes": size,
                            "sha256": digest, "row_count": rows, "etag": obj["etag"]})
        synced = job.get("rowsSynced")
        if synced and int(synced) != total_rows:
            raise IngestionError(f"{dataset} {mes}: Airbyte reported {synced} rows but S3 holds {total_rows}", attempts)
        for entry in entries:
            self.log.append(dataset=dataset, mes=mes, url=url, mode="airbyte", action="synced",
                            airbyte_job_id=str(job.get("jobId")), attempts=attempts, status="ok", **entry)
        IngestionLog.push_metrics(dataset, mes, entries, "synced", attempts, ok=True)
        log.info("%s %s: Airbyte job %s landed %d file(s), %s rows, verified", dataset, mes, job.get("jobId"), len(entries), f"{total_rows:,}")

    def _direct(self, dataset: str, mes: str, url: str, prefix: str, mirror_dir: Path, file_name: str) -> None:
        mirror_dir.mkdir(parents=True, exist_ok=True)
        dest = mirror_dir / file_name

        def download() -> tuple[int, str]:
            tmp = dest.with_name(dest.name + ".part")
            digest, size = hashlib.sha256(), 0
            try:
                with self.http.stream("GET", url) as response:
                    if response.status_code == 404:
                        raise IngestionError(f"{url} not found (HTTP 404): the TLC publishes each month about two months late")
                    if response.status_code == 429 or response.status_code >= 500:
                        raise RetryableError(f"HTTP {response.status_code} from {url}")
                    response.raise_for_status()
                    with tmp.open("wb") as fh:
                        for chunk in response.iter_bytes(CHUNK):
                            fh.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
            except httpx.TransportError as exc:
                raise RetryableError(f"network error downloading {url}: {exc}") from exc
            os.replace(tmp, dest)  # atomic: never a half-written file under the final name
            return size, digest.hexdigest()

        (size, digest), attempts = with_retries(download, what=f"download {dataset} {mes}", sleep=self.sleep)
        for stale in mirror_dir.rglob("*"):  # a single, unmodified file per month
            if stale.is_file() and stale != dest:
                stale.unlink()
        entry = {"file": self.settings.relative(dest), "bytes": size, "sha256": digest, "row_count": count_rows(dest)}
        if self.s3 is not None:
            key = f"{prefix}{file_name}"
            uploaded = self.s3.upload(dest, key)
            stale_keys = [o["key"] for o in self.s3.list(prefix) if o["key"] != key]
            if stale_keys:
                self.s3.delete(stale_keys)
            entry |= {"s3_uri": self.s3.uri(key), "etag": uploaded["etag"]}
        self.log.append(dataset=dataset, mes=mes, url=url, mode="direct", action="downloaded",
                        attempts=attempts, status="ok", **entry)
        IngestionLog.push_metrics(dataset, mes, [entry], "downloaded", attempts, ok=True)
        log.info("%s %s: downloaded %s bytes, sha256=%s..., %s rows", dataset, mes, f"{size:,}", digest[:12], f"{entry['row_count']:,}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", action="append", default=[], help="YYYY-MM (repeatable)")
    parser.add_argument("--setup", action="store_true", help="create the Airbyte source/destination/connections")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        months = [Month.parse(m) for m in args.mes]
        if args.setup:
            client = AirbyteClient(os.environ.get("AIRBYTE_API_URL", ""), os.environ.get("AIRBYTE_CLIENT_ID", ""),
                                   os.environ.get("AIRBYTE_CLIENT_SECRET", ""))
            setup_airbyte(client, months[0] if months else Month(2025, 1))
            return 0
        if not months:
            parser.error("--mes is required")
        with track_step(settings, "ingest", ",".join(m.label for m in months)):
            ingestor = Ingestor(settings)
            ingestor.zones()
            for month in months:
                ingestor.yellow(month)
    except (IngestionError, RetryableError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
