"""Shared fixtures: an isolated data/ folder, settings from env, synthetic TLC files."""
from __future__ import annotations

import os

# Tests never read the developer's .env (credentials, buckets): set before importing src.
os.environ["NYC_TAXI_LOAD_DOTENV"] = "0"
os.environ["PUSHGATEWAY_URL"] = ""
os.environ["LOG_TO_FILE"] = "0"

from datetime import datetime  # noqa: E402
from pathlib import Path

import duckdb  # noqa: E402
import pytest  # noqa: E402

from src.config import Month, Settings  # noqa: E402

ZONES_CSV = '"LocationID","Borough","Zone","service_zone"\n' + "\n".join(
    [
        '1,"EWR","Newark Airport","EWR"',
        '2,"Queens","Jamaica Bay","Boro Zone"',
        '3,"Bronx","Allerton/Pelham Gardens","Boro Zone"',
        '132,"Queens","JFK Airport","Airports"',
        '264,"Unknown","N/A","N/A"',
        '265,"N/A","Outside of NYC","N/A"',
    ]
) + "\n"

TLC_COLUMNS = [
    "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count", "trip_distance",
    "RatecodeID", "store_and_fwd_flag", "PULocationID", "DOLocationID", "payment_type", "fare_amount",
    "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge", "total_amount",
    "congestion_surcharge", "Airport_fee", "cbd_congestion_fee",
]


def trip(**overrides) -> dict:
    """A valid January 2025 trip with the original TLC column names; override any field."""
    row = {
        "VendorID": 2, "tpep_pickup_datetime": datetime(2025, 1, 10, 8, 0), "tpep_dropoff_datetime": datetime(2025, 1, 10, 8, 20),
        "passenger_count": 1, "trip_distance": 3.0, "RatecodeID": 1, "store_and_fwd_flag": "N",
        "PULocationID": 2, "DOLocationID": 3, "payment_type": 1, "fare_amount": 15.0, "extra": 1.0,
        "mta_tax": 0.5, "tip_amount": 3.0, "tolls_amount": 0.0, "improvement_surcharge": 1.0,
        "total_amount": 23.0, "congestion_surcharge": 2.5, "Airport_fee": 0.0, "cbd_congestion_fee": 0.75,
    }
    row.update(overrides)
    return row


def write_tlc_parquet(path: Path, rows: list[dict], columns: list[str] = TLC_COLUMNS) -> Path:
    """Writes rows with TLC names and types (BIGINT passenger_count, INTEGER ids, DOUBLE amounts)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    types = {
        "VendorID": "INTEGER", "PULocationID": "INTEGER", "DOLocationID": "INTEGER", "passenger_count": "BIGINT",
        "RatecodeID": "BIGINT", "payment_type": "BIGINT", "store_and_fwd_flag": "VARCHAR",
        "tpep_pickup_datetime": "TIMESTAMP", "tpep_dropoff_datetime": "TIMESTAMP",
    }
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (" + ", ".join(f'"{c}" {types.get(c, "DOUBLE")}' for c in columns) + ")"
    )
    con.executemany(
        f"INSERT INTO t VALUES ({', '.join('?' for _ in columns)})", [[r.get(c) for c in columns] for r in rows]
    )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT PARQUET)")
    con.close()
    return path


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WAREHOUSE", "duckdb")
    monkeypatch.setenv("INGEST_MODE", "direct")
    monkeypatch.setenv("S3_BUCKET", "")
    monkeypatch.setenv("DUCKDB_MEMORY_LIMIT", "512MB")
    monkeypatch.setenv("DUCKDB_THREADS", "2")
    return Settings.from_env()


@pytest.fixture
def zones_file(settings: Settings) -> Path:
    path = settings.raw_zones_dir / "taxi_zone_lookup.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ZONES_CSV, encoding="utf-8")
    return path


JAN_2025 = Month(2025, 1)
