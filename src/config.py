"""Shared settings, month handling, paths, logging, control database and step metrics."""
from __future__ import annotations

import logging
import os
import re
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import duckdb

try:  # The Makefile exports .env too; loading it here lets modules run from an IDE.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]

# The Makefile exports .env as it is. A .env saved with Windows line endings (CRLF, the default of a Git
# for Windows checkout) would leave a trailing "\r" in every value (an empty passphrase would become
# "\r"). Values are cleaned once here, so every tool started afterwards (dbt, Dagster) gets clean values.
for _name, _value in list(os.environ.items()):
    if _value.endswith("\r"):
        os.environ[_name] = _value.rstrip("\r")

if load_dotenv is not None and os.environ.get("NYC_TAXI_LOAD_DOTENV", "1") != "0":
    load_dotenv(ROOT / ".env", override=False)

# Path settings in .env are portable: "~" is the user's home on Windows, Linux and macOS, and
# relative paths are relative to the repository. They are expanded once here, so every tool
# started afterwards (dbt, Dagster, the Snowflake connector) receives a real absolute path.
PATH_VARIABLES = ("DATA_DIR", "DAGSTER_HOME", "DUCKDB_WAREHOUSE_PATH", "SNOWFLAKE_PRIVATE_KEY_PATH", "SNOWFLAKE_KEYS_DIR")


def resolve_path(value: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(value.strip())))
    return (path if path.is_absolute() else ROOT / path).resolve()


def _normalize_path_variables() -> None:
    for name in PATH_VARIABLES:
        value = os.environ.get(name, "").strip()
        if value:
            os.environ[name] = str(resolve_path(value))
    data_dir = resolve_path(os.environ.get("DATA_DIR", "").strip() or "data")
    os.environ.setdefault("DAGSTER_HOME", str(data_dir / "dagster_home"))
    os.environ.setdefault("DUCKDB_WAREHOUSE_PATH", str(data_dir / "warehouse" / "nyc_taxi.duckdb"))


_normalize_path_variables()

CONTRACTS_DIR = ROOT / "contracts"
SQL_DIR = ROOT / "sql"
TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net"
YELLOW_URL_TEMPLATE = TLC_BASE_URL + "/trip-data/yellow_tripdata_{mes}.parquet"
ZONES_URL = TLC_BASE_URL + "/misc/taxi_zone_lookup.csv"

_MES_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]


# One id per `make all` (the Makefile exports RUN_ID); a fresh one when a module runs alone.
RUN_ID = os.environ.get("RUN_ID") or _new_run_id()


@dataclass(frozen=True, order=True)
class Month:
    """A processed month (the --mes parameter)."""

    year: int
    month: int

    @classmethod
    def parse(cls, value: str) -> "Month":
        match = _MES_RE.match(value.strip())
        if not match:
            raise ValueError(f"--mes must be YYYY-MM (e.g. 2025-01), got {value!r}")
        return cls(int(match.group(1)), int(match.group(2)))

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def comparison(self) -> "Month":
        """Same month of the previous year (exam: assigned month vs the same month of 2024)."""
        return Month(self.year - 1, self.month)

    @property
    def partition(self) -> str:
        """Hive-style partition path."""
        return f"year={self.year:04d}/month={self.month:02d}"

    def __str__(self) -> str:
        return self.label


def months_for(mes: str) -> list[Month]:
    """Assigned month plus its comparison month, in that order."""
    month = Month.parse(mes)
    return [month, month.comparison]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def loopback(url: str) -> str:
    """http://localhost:PORT -> http://127.0.0.1:PORT, for the services of docker compose.

    docker compose publishes its ports on 127.0.0.1 only. On Windows, "localhost" tries IPv6 (::1)
    first, and every refused attempt costs about 2 s before the IPv4 retry: a pipeline run opens
    hundreds of connections (Dagster events, metrics), so it would spend minutes waiting."""
    parsed = urlparse(url)
    if parsed.hostname == "localhost":
        return parsed._replace(netloc=parsed.netloc.replace("localhost", "127.0.0.1", 1)).geturl()
    return url


def dbt_target() -> str:
    """dbt target for this run: DBT_TARGET if set, else duckdb (WAREHOUSE=duckdb), the Snowflake key pair
    (SNOWFLAKE_PRIVATE_KEY_PATH set) or Snowflake browser SSO."""
    if _env("DBT_TARGET"):
        return _env("DBT_TARGET")
    if _env("WAREHOUSE", "snowflake").lower() == "duckdb":
        return "duckdb"
    return "snowflake_keypair" if _env("SNOWFLAKE_PRIVATE_KEY_PATH") else "snowflake_browser"


@dataclass(frozen=True)
class Settings:
    """Run settings. Everything comes from environment variables (.env), never from code."""

    data_dir: Path
    warehouse: str
    ingest_mode: str
    aws_profile: str
    aws_region: str
    s3_bucket: str
    s3_raw_prefix: str
    duckdb_memory_limit: str
    duckdb_threads: int

    @classmethod
    def from_env(cls) -> "Settings":
        warehouse = _env("WAREHOUSE", "snowflake").lower()
        if warehouse not in {"snowflake", "duckdb"}:
            raise ValueError(f"WAREHOUSE must be snowflake or duckdb, got {warehouse!r}")
        ingest_mode = _env("INGEST_MODE", "airbyte").lower()
        if ingest_mode not in {"airbyte", "direct", "hybrid"}:
            raise ValueError(f"INGEST_MODE must be airbyte, direct or hybrid, got {ingest_mode!r}")
        return cls(
            data_dir=resolve_path(_env("DATA_DIR") or "data"),
            warehouse=warehouse,
            ingest_mode=ingest_mode,
            aws_profile=_env("AWS_PROFILE"),
            aws_region=_env("AWS_REGION", "us-east-1"),
            s3_bucket=_env("S3_BUCKET"),
            s3_raw_prefix=_env("S3_RAW_PREFIX", "raw").strip("/"),
            duckdb_memory_limit=_env("DUCKDB_MEMORY_LIMIT", "2GB"),
            duckdb_threads=int(_env("DUCKDB_THREADS", "4")),
        )

    @property
    def offline(self) -> bool:
        """INGEST_MODE=direct WAREHOUSE=duckdb: no cloud at all (S3 is not used even if S3_BUCKET is set)."""
        return self.ingest_mode == "direct" and self.warehouse == "duckdb"

    # --- local layout (data/ is gitignored) -------------------------------------------------
    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def curated_dir(self) -> Path:
        return self.data_dir / "curated"

    @property
    def quarantine_dir(self) -> Path:
        return self.data_dir / "quarantine"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def control_db(self) -> Path:
        return self.data_dir / "control" / "control.duckdb"

    @property
    def warehouse_db(self) -> Path:
        return self.data_dir / "warehouse" / "nyc_taxi.duckdb"

    def raw_month_dir(self, month: Month) -> Path:
        return self.raw_dir / "yellow" / month.partition

    @property
    def raw_zones_dir(self) -> Path:
        return self.raw_dir / "zones"

    def curated_month_dir(self, month: Month) -> Path:
        return self.curated_dir / "yellow" / month.partition

    def quarantine_month_dir(self, month: Month) -> Path:
        return self.quarantine_dir / "yellow" / month.partition

    @property
    def curated_zones_file(self) -> Path:
        return self.curated_dir / "zones" / "taxi_zones.parquet"

    def relative(self, path: Path) -> str:
        """Path relative to data/, with forward slashes (stable across operating systems)."""
        return Path(path).resolve().relative_to(self.data_dir).as_posix()

    def s3_prefix(self, dataset: str, month: Month | None = None) -> str:
        base = f"{self.s3_raw_prefix}/{dataset}"
        return f"{base}/{month.partition}/" if month else f"{base}/"


def get_logger(name: str) -> logging.Logger:
    """stdout (terminal and Dozzle) plus JSON lines in data/logs/pipeline.jsonl (Alloy -> Loki)."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=_env("LOG_LEVEL", "INFO"),
            format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
            stream=sys.stdout,
        )
        from src.observability import json_file_handler

        handler = json_file_handler(resolve_path(_env("DATA_DIR") or "data"), RUN_ID)
        if handler is not None:
            root.addHandler(handler)
        for noisy in ("httpx", "botocore", "boto3", "urllib3", "snowflake.connector", "alembic"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    return logging.getLogger(name)


def configure_duckdb(con: duckdb.DuckDBPyConnection, settings: Settings) -> duckdb.DuckDBPyConnection:
    """Memory-safe DuckDB session for an 8 GB laptop. UTC so timestamps are never shifted."""
    spill = settings.data_dir / "tmp" / "duckdb"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"SET memory_limit = '{settings.duckdb_memory_limit}'")
    con.execute(f"SET threads = {settings.duckdb_threads}")
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET temp_directory = '{spill.as_posix()}'")
    return con


CONTROL_DDL = (
    """CREATE TABLE IF NOT EXISTS ingestion_log (
        run_id VARCHAR, dataset VARCHAR, mes VARCHAR, file VARCHAR, url VARCHAR, s3_uri VARCHAR,
        bytes BIGINT, sha256 VARCHAR, row_count BIGINT, etag VARCHAR, mode VARCHAR, action VARCHAR,
        airbyte_job_id VARCHAR, attempts INTEGER, status VARCHAR, error VARCHAR, logged_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS schema_report (
        run_id VARCHAR, dataset VARCHAR, mes VARCHAR, files VARCHAR, missing_required VARCHAR,
        missing_optional VARCHAR, new_columns VARCHAR, type_mismatches VARCHAR, cast_failures VARCHAR,
        null_violations VARCHAR, status VARCHAR, created_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS quality_summary (
        run_id VARCHAR, mes VARCHAR, rows_read BIGINT, rows_accepted BIGINT, rows_quarantined BIGINT,
        rows_with_warnings BIGINT, reconciled BOOLEAN, created_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS quality_report (
        run_id VARCHAR, mes VARCHAR, rule_id VARCHAR, name VARCHAR, severity VARCHAR, threshold VARCHAR,
        violations BIGINT, pct_of_read DOUBLE, created_at TIMESTAMP)""",
    """CREATE TABLE IF NOT EXISTS run_metrics (
        run_id VARCHAR, step VARCHAR, mes VARCHAR, seconds DOUBLE, peak_rss_mb DOUBLE, ok BOOLEAN,
        created_at TIMESTAMP)""",
)


def connect_duckdb_file(path: Path, *, read_only: bool = False, attempts: int = 8) -> duckdb.DuckDBPyConnection:
    """Opens a DuckDB file, retrying briefly when another process (sync client, antivirus) holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            return duckdb.connect(str(path), read_only=read_only)
        except duckdb.IOException:
            if attempt == attempts:
                raise
            time.sleep(0.25 * attempt)
    raise RuntimeError("unreachable")


def control_db(settings: Settings) -> duckdb.DuckDBPyConnection:
    """Local control database: ingestion_log, schema/quality reports and run metrics."""
    con = connect_duckdb_file(settings.control_db)
    for ddl in CONTROL_DDL:
        con.execute(ddl)
    return con


def peak_rss_mb() -> float | None:
    """Peak resident memory of this process (DuckDB runs in-process, so it is included)."""
    try:
        import psutil

        peak = getattr(psutil.Process().memory_info(), "peak_wset", None)  # Windows
        if peak:
            return round(peak / 1e6, 1)
    except Exception:  # pragma: no cover - psutil missing or restricted
        pass
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(value / 1e6 if sys.platform == "darwin" else value / 1e3, 1)
    except Exception:  # pragma: no cover
        return None


@contextmanager
def track_step(settings: Settings, step: str, mes: str = "-") -> Iterator[None]:
    """Logs duration and peak RAM of a step and stores them in run_metrics (README numbers)."""
    log = get_logger("metrics")
    start = time.perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        seconds = round(time.perf_counter() - start, 2)
        peak = peak_rss_mb()
        log.info("step=%s mes=%s seconds=%.2f peak_rss_mb=%s ok=%s", step, mes, seconds, peak, ok)
        from src.observability import push_step

        push_step(step, mes, seconds, peak, ok)
        with control_db(settings) as con:
            con.execute(
                "INSERT INTO run_metrics VALUES (?, ?, ?, ?, ?, ?, now())",
                [RUN_ID, step, mes, seconds, peak, ok],
            )


def _cli(argv: list[str]) -> int:
    """Tiny helper used by the Makefile: `months 2025-01` and `run-id`."""
    # end="": no trailing newline, so make's $(shell ...) never keeps a Windows "\r".
    if len(argv) == 2 and argv[0] == "months":
        print(" ".join(m.label for m in months_for(argv[1])), end="")
        return 0
    if argv == ["run-id"]:
        print(_new_run_id(), end="")
        return 0
    print("usage: python -m src.config months YYYY-MM | run-id", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
