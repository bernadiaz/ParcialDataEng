"""Load step (DuckDB -> Snowflake RAW). Bridge between Part 3 and the dbt model.

For each month, the curated Parquet written by DuckDB is loaded into RAW.YELLOW_TRIPS in a
single transaction: the rows of that (year, month) are deleted, the file is loaded with COPY INTO
from an internal stage, and the loaded rows are checked against the curated count. If anything
fails the transaction rolls back, so reprocessing a month replaces only that month. The zone
lookup is reloaded the same way into RAW.TAXI_ZONES. Every load writes a row to RAW.LOAD_LOG
(rows deleted, rows loaded, file SHA-256, run id), which the oral defense uses.

WAREHOUSE=duckdb runs the same logic against data/warehouse/nyc_taxi.duckdb (offline validation).

    python -m src.load_snowflake --mes 2025-01 --mes 2024-01
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from src import esquema
from src.config import RUN_ID, Month, Settings, connect_duckdb_file, get_logger, track_step
from src.ingesta_airbyte import sha256_file
from src.observability import push

log = get_logger("load")

SNOWFLAKE_TYPES = {
    "INTEGER": "INTEGER", "BIGINT": "INTEGER", "SMALLINT": "SMALLINT", "DOUBLE": "FLOAT",
    "VARCHAR": "VARCHAR", "TIMESTAMP": "TIMESTAMP_NTZ", "BOOLEAN": "BOOLEAN", "DATE": "DATE",
}
LINEAGE_COLUMNS = (
    ("source_file", "VARCHAR"), ("source_row_number", "BIGINT"), ("quality_flags", "VARCHAR"),
    ("year", "SMALLINT"), ("month", "SMALLINT"), ("run_id", "VARCHAR"),
)


class LoadError(RuntimeError):
    """The warehouse did not end with exactly the curated rows of the month."""


@dataclass
class LoadResult:
    table: str
    mes: str
    rows_deleted: int
    rows_loaded: int


def trips_columns() -> list[tuple[str, str]]:
    """RAW.YELLOW_TRIPS columns, generated from the contract (single source of truth)."""
    contract = esquema.load_contract(esquema.YELLOW_CONTRACT)
    return [(c["name"], c["type"].upper()) for c in contract["columns"]] + list(LINEAGE_COLUMNS)


def zones_columns() -> list[tuple[str, str]]:
    contract = esquema.load_contract(esquema.ZONES_CONTRACT)
    return [(c["name"], c["type"].upper()) for c in contract["columns"]]


def parquet_rows(path: Path) -> int:
    with duckdb.connect() as con:
        return con.execute(f"SELECT count(*) FROM read_parquet('{path.as_posix()}')").fetchone()[0]


# --- Snowflake -------------------------------------------------------------------------------------
def query_tag(step: str) -> str:
    env = os.environ.get("COST_ENV", "dev")
    owner = os.environ.get("COST_OWNER", "unknown")
    return f"project=nyc_taxi;env={env};owner={owner};step={step}"


def snowflake_connect(step: str = "load") -> Any:
    """Connection from .env: key pair when SNOWFLAKE_PRIVATE_KEY_PATH is set, otherwise
    SNOWFLAKE_AUTHENTICATOR (externalbrowser = SSO in the browser, token cached locally)."""
    import snowflake.connector

    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise LoadError(f"Missing Snowflake settings in .env: {missing}")
    kwargs: dict[str, Any] = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"].strip(),
        "user": os.environ["SNOWFLAKE_USER"].strip(),
        "role": os.environ["SNOWFLAKE_ROLE"].strip(),
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"].strip(),
        "database": os.environ["SNOWFLAKE_DATABASE"].strip(),
        "schema": "RAW",
        "session_parameters": {"QUERY_TAG": query_tag(step)},
        "client_session_keep_alive": False,
    }
    key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH", "").strip()
    if key_path:
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        kwargs["private_key_file"] = key_path
        passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").strip()
        if passphrase:
            kwargs["private_key_file_pwd"] = passphrase
    else:
        kwargs["authenticator"] = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "externalbrowser").strip()
        kwargs["client_store_temporary_credential"] = True  # one browser login per session
    return snowflake.connector.connect(**kwargs)


class SnowflakeWarehouse:
    STAGE = "RAW.TAXI_STAGE"

    def __init__(self, connection: Any | None = None):
        self.conn = connection or snowflake_connect()

    def close(self) -> None:
        self.conn.close()

    def execute(self, sql: str, params: Any = None) -> list[tuple]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            try:
                return cur.fetchall()
            except Exception:  # statements without a result set
                return []

    def _copy(self, sql: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            names = [d[0].lower() for d in cur.description or []]
        if "rows_loaded" not in names:  # "Copy executed with 0 files processed."
            return 0
        index = names.index("rows_loaded")
        return sum(int(row[index]) for row in rows)

    def ensure_objects(self) -> None:
        """Tables are created by the pipeline role. Database, schemas and warehouses come from snowflake/setup.sql."""
        trips = ",\n  ".join(f"{name.upper()} {SNOWFLAKE_TYPES[kind]}" for name, kind in trips_columns())
        zones = ",\n  ".join(f"{name.upper()} {SNOWFLAKE_TYPES[kind]}" for name, kind in zones_columns())
        self.execute(f"CREATE TABLE IF NOT EXISTS RAW.YELLOW_TRIPS (\n  {trips}\n)")
        self.execute(f"CREATE TABLE IF NOT EXISTS RAW.TAXI_ZONES (\n  {zones}\n)")
        self.execute(
            """CREATE TABLE IF NOT EXISTS RAW.LOAD_LOG (
                 RUN_ID VARCHAR, MES VARCHAR, TARGET_TABLE VARCHAR, SOURCE_FILE VARCHAR, SOURCE_SHA256 VARCHAR,
                 ROWS_DELETED INTEGER, ROWS_LOADED INTEGER, LOADED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP())"""
        )
        self.execute(f"CREATE STAGE IF NOT EXISTS {self.STAGE} FILE_FORMAT = (TYPE = PARQUET)")

    def replace(self, table: str, mes: str, parquet: Path, where: str, params: dict[str, Any], expected: int) -> LoadResult:
        stage_dir = f"{self.STAGE}/{table.split('.')[-1].lower()}/{mes.replace('-', '_')}"
        self.execute(f"REMOVE @{stage_dir}/")
        self.execute(f"PUT 'file://{parquet.resolve().as_posix()}' @{stage_dir} OVERWRITE = TRUE AUTO_COMPRESS = FALSE")
        digest = sha256_file(parquet)
        self.execute("BEGIN")
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"DELETE FROM {table} WHERE {where}", params)
                deleted = cur.rowcount or 0
            loaded = self._copy(
                f"""COPY INTO {table} FROM @{stage_dir}/
                    FILE_FORMAT = (TYPE = PARQUET USE_LOGICAL_TYPE = TRUE)
                    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
                    ON_ERROR = ABORT_STATEMENT
                    FORCE = TRUE"""
            )
            if loaded != expected:
                raise LoadError(f"{table} {mes}: loaded {loaded:,} rows, curated file has {expected:,}")
            self.execute(
                "INSERT INTO RAW.LOAD_LOG (RUN_ID, MES, TARGET_TABLE, SOURCE_FILE, SOURCE_SHA256, ROWS_DELETED, ROWS_LOADED) "
                "VALUES (%(run)s, %(mes)s, %(table)s, %(file)s, %(sha)s, %(deleted)s, %(loaded)s)",
                {"run": RUN_ID, "mes": mes, "table": table, "file": parquet.name, "sha": digest,
                 "deleted": deleted, "loaded": loaded},
            )
            self.execute("COMMIT")
        except Exception:
            self.execute("ROLLBACK")
            raise
        finally:
            self.execute(f"REMOVE @{stage_dir}/")  # FinOps: no stage storage left behind
        return LoadResult(table, mes, deleted, loaded)

    def replace_month(self, month: Month, parquet: Path, expected: int) -> LoadResult:
        return self.replace("RAW.YELLOW_TRIPS", month.label, parquet, "YEAR = %(year)s AND MONTH = %(month)s",
                            {"year": month.year, "month": month.month}, expected)

    def replace_zones(self, parquet: Path, expected: int) -> LoadResult:
        return self.replace("RAW.TAXI_ZONES", "static", parquet, "TRUE", {}, expected)


# --- DuckDB (offline validation target) ---------------------------------------------------------------
class DuckDBWarehouse:
    """Same contract as SnowflakeWarehouse on a local file, so dbt and q1..q6 can run without a cloud account."""

    def __init__(self, settings: Settings):
        self.conn = connect_duckdb_file(settings.warehouse_db)
        self.conn.execute("SET TimeZone = 'UTC'")

    def close(self) -> None:
        self.conn.close()

    def ensure_objects(self) -> None:
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        trips = ", ".join(f"{name} {kind}" for name, kind in trips_columns())
        zones = ", ".join(f"{name} {kind}" for name, kind in zones_columns())
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS raw.yellow_trips ({trips})")
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS raw.taxi_zones ({zones})")
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS raw.load_log (run_id VARCHAR, mes VARCHAR, target_table VARCHAR,
               source_file VARCHAR, source_sha256 VARCHAR, rows_deleted BIGINT, rows_loaded BIGINT,
               loaded_at TIMESTAMP DEFAULT current_timestamp)"""
        )

    def replace(self, table: str, mes: str, parquet: Path, where: str, params: list[Any], expected: int) -> LoadResult:
        self.conn.execute("BEGIN TRANSACTION")
        try:
            deleted = self.conn.execute(f"DELETE FROM {table} WHERE {where}", params).fetchone()[0]
            self.conn.execute(
                f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet('{parquet.as_posix()}', hive_partitioning = false)"
            )
            loaded = self.conn.execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()[0]
            if loaded != expected:
                raise LoadError(f"{table} {mes}: loaded {loaded:,} rows, curated file has {expected:,}")
            self.conn.execute(
                "INSERT INTO raw.load_log (run_id, mes, target_table, source_file, source_sha256, rows_deleted, rows_loaded) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [RUN_ID, mes, table, parquet.name, sha256_file(parquet), deleted, loaded],
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return LoadResult(table, mes, deleted, loaded)

    def replace_month(self, month: Month, parquet: Path, expected: int) -> LoadResult:
        return self.replace("raw.yellow_trips", month.label, parquet, "year = ? AND month = ?", [month.year, month.month], expected)

    def replace_zones(self, parquet: Path, expected: int) -> LoadResult:
        return self.replace("raw.taxi_zones", "static", parquet, "TRUE", [], expected)


def open_warehouse(settings: Settings) -> SnowflakeWarehouse | DuckDBWarehouse:
    return DuckDBWarehouse(settings) if settings.warehouse == "duckdb" else SnowflakeWarehouse()


def load_zones(settings: Settings, warehouse: Any) -> LoadResult:
    zones_file = settings.curated_zones_file
    if not zones_file.exists():
        raise LoadError(f"{zones_file} not found: run `make quality` first")
    return warehouse.replace_zones(zones_file, parquet_rows(zones_file))


def load_month(settings: Settings, warehouse: Any, month: Month) -> LoadResult:
    parquet = settings.curated_month_dir(month) / "part-0.parquet"
    if not parquet.exists():
        raise LoadError(f"{parquet} not found: run `make quality MES={month}` first")
    return warehouse.replace_month(month, parquet, parquet_rows(parquet))


def load_months(
    settings: Settings, months: list[Month], warehouse: Any | None = None, *, include_zones: bool = True
) -> list[LoadResult]:
    own = warehouse is None
    warehouse = warehouse or open_warehouse(settings)
    results = []
    try:
        warehouse.ensure_objects()
        if include_zones:
            results.append(load_zones(settings, warehouse))
        for month in months:
            results.append(load_month(settings, warehouse, month))
        for r in results:
            log.info("load %s %s: deleted=%s loaded=%s", r.table, r.mes, f"{r.rows_deleted:,}", f"{r.rows_loaded:,}")
            labels = {"table": r.table.lower(), "warehouse": settings.warehouse}
            push("load", r.mes, [
                ("nyc_taxi_loaded_rows", "Rows loaded into the warehouse for the month", labels, float(r.rows_loaded)),
                ("nyc_taxi_deleted_rows", "Rows replaced (deleted before the load)", labels, float(r.rows_deleted)),
            ])
    finally:
        if own:
            warehouse.close()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", action="append", required=True, help="YYYY-MM (repeatable)")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    months = [Month.parse(m) for m in args.mes]
    try:
        with track_step(settings, f"load-{settings.warehouse}", ",".join(m.label for m in months)):
            load_months(settings, months)
    except LoadError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
