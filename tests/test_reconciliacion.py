"""Reconciliation: rows read = accepted + quarantined, in the quality gate and in the warehouse load."""
from __future__ import annotations

from pathlib import Path

import pytest

from src import calidad, load_snowflake
from src.config import Month
from tests.conftest import JAN_2025, trip, write_tlc_parquet


def test_reconcile_accepts_balanced_counts_and_rejects_the_rest():
    calidad.reconcile(10, 7, 3)
    with pytest.raises(calidad.ReconciliationError):
        calidad.reconcile(10, 7, 2)


def test_quality_step_fails_and_keeps_the_previous_partition_when_counts_do_not_reconcile(settings, zones_file, monkeypatch):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip(), trip(trip_distance=0.0)])
    first = calidad.run_month(settings, JAN_2025)
    before = first.curated_file.read_bytes()

    def broken(rows_read, rows_accepted, rows_quarantined, mes=""):
        raise calidad.ReconciliationError("simulated mismatch")

    monkeypatch.setattr(calidad, "reconcile", broken)
    with pytest.raises(calidad.ReconciliationError):
        calidad.run_month(settings, JAN_2025)
    assert first.curated_file.read_bytes() == before        # the published partition was not replaced
    assert calidad.main(["--mes", "2025-01"]) == 1           # non-zero exit code for make


class FakeCursor:
    """Records SQL. COPY reports `copy_rows` loaded rows."""

    def __init__(self, log: list[str], copy_rows: int):
        self.log, self.copy_rows, self.description, self.rowcount, self._rows = log, copy_rows, None, 0, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        verb = sql.split()[0].upper()
        self.log.append(verb)
        if verb == "COPY":
            self.description = [("file",), ("status",), ("rows_parsed",), ("rows_loaded",)]
            self._rows = [("part-0.parquet", "LOADED", self.copy_rows, self.copy_rows)]
        else:
            self.description, self._rows = None, []
        return self

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, copy_rows: int):
        self.log: list[str] = []
        self.copy_rows = copy_rows

    def cursor(self):
        return FakeCursor(self.log, self.copy_rows)

    def close(self):
        pass


def _curated(tmp_path: Path, rows: int) -> Path:
    path = tmp_path / "part-0.parquet"
    write_tlc_parquet(path, [trip() for _ in range(rows)])
    return path


def test_snowflake_load_rolls_back_when_loaded_rows_differ(tmp_path):
    conn = FakeConnection(copy_rows=4)
    warehouse = load_snowflake.SnowflakeWarehouse(connection=conn)
    with pytest.raises(load_snowflake.LoadError):
        warehouse.replace_month(Month(2025, 1), _curated(tmp_path, 5), expected=5)
    assert "ROLLBACK" in conn.log and "COMMIT" not in conn.log


def test_snowflake_load_deletes_only_the_month_and_commits(tmp_path):
    conn = FakeConnection(copy_rows=5)
    warehouse = load_snowflake.SnowflakeWarehouse(connection=conn)
    result = warehouse.replace_month(Month(2025, 1), _curated(tmp_path, 5), expected=5)
    assert result.rows_loaded == 5
    assert conn.log[conn.log.index("BEGIN"):] == ["BEGIN", "DELETE", "COPY", "INSERT", "COMMIT", "REMOVE"]
