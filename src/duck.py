"""Helpers DuckDB con límites de memoria para notebooks ~8 GB."""

from __future__ import annotations

import duckdb

from src.config import Settings, get_settings


def connect(settings: Settings | None = None) -> duckdb.DuckDBPyConnection:
    settings = settings or get_settings()
    con = duckdb.connect(database=":memory:")
    con.execute(f"SET threads TO {settings.duckdb_threads}")
    con.execute(f"SET memory_limit TO '{settings.duckdb_memory_limit}'")
    con.execute("SET enable_progress_bar TO false")
    return con


def configure_s3(con: duckdb.DuckDBPyConnection, settings: Settings) -> None:
    """Instala httpfs y configura credenciales S3 / MinIO."""
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='{settings.s3_region}'")
    if settings.s3_access_key_id:
        con.execute(f"SET s3_access_key_id='{settings.s3_access_key_id}'")
    if settings.s3_secret_access_key:
        con.execute(f"SET s3_secret_access_key='{settings.s3_secret_access_key}'")
    if settings.s3_endpoint_url:
        # DuckDB espera host[:port] sin esquema
        endpoint = settings.s3_endpoint_url.replace("https://", "").replace("http://", "")
        con.execute(f"SET s3_endpoint='{endpoint}'")
        con.execute(f"SET s3_url_style='{'path' if settings.s3_path_style else 'vhost'}'")
        con.execute(f"SET s3_use_ssl={'true' if settings.s3_use_ssl else 'false'}")
