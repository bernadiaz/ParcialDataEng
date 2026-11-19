"""Dagster instance (run history) shared by `make all` on the host and the Dagster UI in Docker.

`docker compose up -d` starts a Postgres for Dagster (127.0.0.1:DAGSTER_PG_PORT, default 5434) and
the Dagster UI (http://localhost:3003). When that Postgres answers, this module points
DAGSTER_HOME/dagster.yaml at it. Every run of `make all` (its materializations, metadata and checks)
then shows up in the UI right away, on Windows, Linux and macOS alike, because the host and the
container read the same history. Without Docker, the history falls back to SQLite files in
DAGSTER_HOME, and `make dagster-ui` shows it.

DAGSTER_STORAGE chooses the storage:
    auto      Postgres when it answers, otherwise SQLite (default)
    postgres  Postgres only. It waits for it and fails if it never answers (the UI container uses it).
    sqlite    SQLite files in DAGSTER_HOME

    python -m src.dagster_instance            # writes dagster.yaml and prints the storage in use
    python -m src.dagster_instance --wipe     # empties the run history (make clean)
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from pathlib import Path

from src.config import get_logger

log = get_logger("dagster-instance")

# Defaults match docker-compose.yml, so a .env without these variables still works. The host is
# 127.0.0.1, not localhost: see src.config.loopback (Windows would spend ~2 s on every connection).
PG_DEFAULTS = {
    "DAGSTER_PG_HOST": "127.0.0.1",
    "DAGSTER_PG_PORT": "5434",
    "DAGSTER_PG_USER": "dagster",
    "DAGSTER_PG_PASSWORD": "dagster",
    "DAGSTER_PG_DB": "dagster",
}
for _name, _value in PG_DEFAULTS.items():
    if not os.environ.get(_name, "").strip():
        os.environ[_name] = _value
if os.environ["DAGSTER_PG_HOST"].strip() == "localhost":
    os.environ["DAGSTER_PG_HOST"] = "127.0.0.1"

HEADER = "# Written by src/dagster_instance.py (do not edit: it is rewritten on every make all).\n"
POSTGRES_YAML = """\
storage:
  postgres:
    postgres_db:
      hostname: {env: DAGSTER_PG_HOST}
      port: {env: DAGSTER_PG_PORT}
      username: {env: DAGSTER_PG_USER}
      password: {env: DAGSTER_PG_PASSWORD}
      db_name: {env: DAGSTER_PG_DB}
"""
TELEMETRY_YAML = "telemetry:\n  enabled: false\n"
# The UI container reads the step logs (stdout/stderr) that runs on Linux/macOS hosts write.
COMPUTE_LOGS_YAML = """\
compute_logs:
  module: dagster._core.storage.local_compute_log_manager
  class: LocalComputeLogManager
  config:
    base_dir: {env: DAGSTER_COMPUTE_LOGS_DIR}
"""


def dagster_home() -> Path:
    home = Path(os.environ["DAGSTER_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    return home


def _pg_address() -> tuple[str, int]:
    return os.environ["DAGSTER_PG_HOST"].strip(), int(os.environ["DAGSTER_PG_PORT"].strip())


def _port_refused(host: str, port: int) -> bool:
    """True when nothing listens on host:port (Docker is not running the stack)."""
    try:
        socket.create_connection((host, port), timeout=2).close()
        return False
    except ConnectionRefusedError:
        return True
    except OSError:  # timeout, unknown host: let the real connection attempt decide
        return False


def postgres_ready(wait_seconds: float, *, required: bool = False) -> bool:
    """Waits until Postgres accepts a login (a container that just started needs a few seconds)."""
    import psycopg2

    host, port = _pg_address()
    deadline = time.monotonic() + wait_seconds
    while True:
        if not required and _port_refused(host, port):
            return False
        try:
            psycopg2.connect(host=host, port=port, user=os.environ["DAGSTER_PG_USER"],
                             password=os.environ["DAGSTER_PG_PASSWORD"], dbname=os.environ["DAGSTER_PG_DB"],
                             connect_timeout=3).close()
            return True
        except psycopg2.OperationalError as exc:
            if time.monotonic() >= deadline:
                log.warning("Dagster Postgres at %s:%s did not accept a connection: %s", host, port, str(exc).strip())
                return False
            time.sleep(2)


def configure(*, quiet: bool = False) -> str:
    """Writes DAGSTER_HOME/dagster.yaml for the storage in use and returns "postgres" or "sqlite"."""
    mode = os.environ.get("DAGSTER_STORAGE", "auto").strip().lower() or "auto"
    if mode not in {"auto", "postgres", "sqlite"}:
        raise ValueError(f"DAGSTER_STORAGE must be auto, postgres or sqlite, got {mode!r}")
    if mode == "sqlite":
        storage = "sqlite"
    elif mode == "postgres":
        if not postgres_ready(180, required=True):
            raise RuntimeError("DAGSTER_STORAGE=postgres but the Dagster Postgres never answered")
        storage = "postgres"
    else:
        storage = "postgres" if postgres_ready(60) else "sqlite"

    text = HEADER + (POSTGRES_YAML if storage == "postgres" else "") + TELEMETRY_YAML
    if os.environ.get("DAGSTER_COMPUTE_LOGS_DIR", "").strip():
        text += COMPUTE_LOGS_YAML
    path = dagster_home() / "dagster.yaml"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    nux = path.parent / ".nux" / "nux.yaml"  # skip the "Join the Dagster community" popup of a new instance
    if not nux.exists():
        nux.parent.mkdir(parents=True, exist_ok=True)
        nux.write_text("seen: 1\n", encoding="utf-8")

    if not quiet:
        if storage == "postgres":
            host, port = _pg_address()
            log.info("Dagster run history: Postgres %s:%s (shown live in the Dagster UI of docker compose)", host, port)
        else:
            log.warning("Dagster run history: SQLite in %s. The Postgres of docker compose is not running, so the "
                        "Dagster UI in Docker will not show these runs (start it with `docker compose up -d`, or "
                        "open the local UI with `make dagster-ui`).", path.parent)
    return storage


def wipe() -> None:
    """Deletes every run, materialization and month partition (make clean)."""
    from dagster import DagsterInstance

    storage = configure(quiet=True)
    instance = DagsterInstance.get()
    for key in instance.get_dynamic_partitions("months"):
        instance.delete_dynamic_partition("months", key)
    instance.wipe()
    log.info("Dagster run history wiped (%s)", storage)


def register_months(mes: str) -> list[str]:
    """Adds MES and its comparison month as partitions of the monthly assets (idempotent).

    A month partition set with no months renders as "0 of 0 materialized" (a green check) in the UI,
    next to grey never-materialized assets, which looks like a half-finished run. Registering the
    months up front makes a new UI honest: every asset grey until `make all` materializes it."""
    from dagster import DagsterInstance

    from src.config import months_for

    labels = [m.label for m in months_for(mes)]
    instance = DagsterInstance.get()
    new = [label for label in labels if not instance.has_dynamic_partition("months", label)]
    if new:
        instance.add_dynamic_partitions("months", new)
    return labels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wipe", action="store_true", help="delete the whole run history")
    parser.add_argument("--months", metavar="YYYY-MM", help="also register this month and its comparison month")
    args = parser.parse_args(argv)
    if args.wipe:
        wipe()
        return 0
    print(configure())
    if args.months:
        print("months:", ", ".join(register_months(args.months)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
