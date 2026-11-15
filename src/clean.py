"""make clean: start from scratch on this computer.

Empties DATA_DIR (raw mirror, curated, quarantine, reports, logs, control database, DuckDB warehouse
and the Dagster history) and removes the dbt artifacts. It keeps:
  - DATA_DIR/superset_home: the Superset metadata (dashboards survive a clean);
  - the folders that docker compose mounts (logs, bi, dagster_home/storage). They are emptied, not
    deleted, so the running containers keep seeing them.
The Dagster run history is wiped too, in the Postgres of docker compose or in SQLite.

    python -m src.clean
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ["LOG_TO_FILE"] = "0"  # this process must not hold DATA_DIR/logs/pipeline.jsonl open while deleting it

from src.config import ROOT, Settings  # noqa: E402

KEEP = {"superset_home"}
MOUNTED = ("logs", "bi", "dagster_home/storage")


def _remove(path: Path) -> None:
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    except OSError as exc:  # e.g. a file another program still holds open on Windows
        print(f"Could not delete {path}: {exc}", file=sys.stderr)


def _clear(directory: Path, data_dir: Path, mounted: set[Path]) -> None:
    for child in sorted(directory.iterdir()):
        if directory == data_dir and child.name in KEEP:
            continue
        if child in mounted:
            for inner in child.iterdir():
                _remove(inner)
        elif child.is_dir() and any(m.is_relative_to(child) for m in mounted):
            _clear(child, data_dir, mounted)
        else:
            _remove(child)


def clean(settings: Settings) -> None:
    try:
        from src import dagster_instance

        dagster_instance.wipe()
    except Exception as exc:  # noqa: BLE001 - a missing history must never block a clean
        print(f"Dagster history not wiped ({exc.__class__.__name__}: {exc})", file=sys.stderr)
    data_dir = settings.data_dir
    mounted = {data_dir / m for m in MOUNTED}
    if data_dir.is_dir():
        _clear(data_dir, data_dir, mounted)
    for path in mounted:
        path.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "dbt_taxi" / "target", ROOT / "dbt_taxi" / "logs"):
        shutil.rmtree(path, ignore_errors=True)
    print(f"Clean: {data_dir} emptied (kept superset_home and the folders docker compose mounts)")


if __name__ == "__main__":
    clean(Settings.from_env())
