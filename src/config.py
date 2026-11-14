"""Configuración por ambiente (dev / prod).

Carga, en orden:
1. environments/{ENV}.env
2. variables de entorno del proceso / Docker
3. .env (vía python-dotenv si está disponible)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse_env_file(path: Path, *, override: bool) -> None:
    """Carga KEY=VALUE sin depender de python-dotenv (útil en smoke local)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def _load_dotenv_files(env_name: str) -> None:
    # 1) defaults del ambiente  2) secretos .env pisan
    _parse_env_file(ROOT / "environments" / f"{env_name}.env", override=False)
    _parse_env_file(ROOT / ".env", override=True)
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / "environments" / f"{env_name}.env", override=False)
    load_dotenv(ROOT / ".env", override=True)


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str
    mes: str | None
    data_dir: Path
    s3_endpoint_url: str | None
    s3_access_key_id: str | None
    s3_secret_access_key: str | None
    s3_bucket: str
    s3_region: str
    s3_use_ssl: bool
    s3_path_style: bool
    s3_raw_prefix: str
    s3_control_prefix: str
    duckdb_threads: int
    duckdb_memory_limit: str
    max_distance_miles: float
    cbd_fee_missing_strategy: str
    ingest_max_retries: int
    skip_snowflake: bool
    skip_dbt: bool
    airbyte_enabled: bool
    snowflake_account: str | None
    snowflake_user: str | None
    snowflake_warehouse: str | None
    snowflake_database: str | None
    snowflake_schema_raw: str
    snowflake_schema_staging: str
    snowflake_schema_marts: str

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    def raw_yellow_key(self, year: int, month: int, filename: str) -> str:
        return f"{self.s3_raw_prefix}/yellow/year={year:04d}/month={month:02d}/{filename}"

    def raw_zones_key(self) -> str:
        return f"{self.s3_raw_prefix}/zones/taxi_zone_lookup.csv"


def get_settings(mes: str | None = None) -> Settings:
    env_name = os.getenv("ENV", os.getenv("APP_ENV", "dev")).strip().lower()
    _load_dotenv_files(env_name)

    data_dir = Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve()

    return Settings(
        env=env_name,
        mes=mes or os.getenv("MES"),
        data_dir=data_dir,
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
        s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        s3_bucket=os.getenv("S3_BUCKET", "nyc-taxi"),
        s3_region=os.getenv("S3_REGION", "us-east-1"),
        s3_use_ssl=_bool(os.getenv("S3_USE_SSL"), default=env_name != "dev"),
        s3_path_style=_bool(os.getenv("S3_PATH_STYLE"), default=env_name == "dev"),
        s3_raw_prefix=os.getenv("S3_RAW_PREFIX", "raw"),
        s3_control_prefix=os.getenv("S3_CONTROL_PREFIX", "control"),
        duckdb_threads=int(os.getenv("DUCKDB_THREADS", "2")),
        duckdb_memory_limit=os.getenv("DUCKDB_MEMORY_LIMIT", "2GB"),
        max_distance_miles=float(os.getenv("MAX_DISTANCE_MILES", "100")),
        cbd_fee_missing_strategy=os.getenv("CBD_FEE_MISSING_STRATEGY", "null"),
        ingest_max_retries=int(os.getenv("INGEST_MAX_RETRIES", "3")),
        skip_snowflake=_bool(os.getenv("SKIP_SNOWFLAKE"), default=env_name == "dev"),
        skip_dbt=_bool(os.getenv("SKIP_DBT"), default=env_name == "dev"),
        airbyte_enabled=_bool(os.getenv("AIRBYTE_ENABLED"), default=False),
        snowflake_account=os.getenv("SNOWFLAKE_ACCOUNT"),
        snowflake_user=os.getenv("SNOWFLAKE_USER"),
        snowflake_warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "WH_TAXI_RUN"),
        snowflake_database=os.getenv("SNOWFLAKE_DATABASE", "NYC_TAXI"),
        snowflake_schema_raw=os.getenv("SNOWFLAKE_SCHEMA_RAW", "RAW"),
        snowflake_schema_staging=os.getenv("SNOWFLAKE_SCHEMA_STAGING", "STAGING"),
        snowflake_schema_marts=os.getenv("SNOWFLAKE_SCHEMA_MARTS", "MARTS"),
    )
