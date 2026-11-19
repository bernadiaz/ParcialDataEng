"""Quality rules on synthetic data: each row is built to hit one rule."""
from __future__ import annotations

from datetime import datetime

import duckdb

from src import calidad
from tests.conftest import JAN_2025, trip, write_tlc_parquet


def _read(path):
    con = duckdb.connect()
    cursor = con.execute(f"SELECT * FROM read_parquet('{path.as_posix()}', hive_partitioning = false)")
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def test_rules_split_rows_between_curated_and_quarantine(settings, zones_file):
    good = trip()
    rows = [
        good,
        trip(tpep_dropoff_datetime=datetime(2025, 1, 10, 7, 59)),               # R02 dropoff before pickup
        trip(tpep_pickup_datetime=datetime(2025, 2, 1, 0, 5),
             tpep_dropoff_datetime=datetime(2025, 2, 1, 0, 25)),                # R01 other month
        dict(good),                                                             # R07 exact duplicate
        trip(passenger_count=None),                                             # R05 warning only
        trip(PULocationID=999),                                                 # R06 unknown zone
        trip(trip_distance=150.0, tpep_dropoff_datetime=datetime(2025, 1, 10, 11, 0)),  # R03 above max (50 mph)
        trip(trip_distance=20.0, tpep_dropoff_datetime=datetime(2025, 1, 10, 8, 5)),  # R09 240 mph
        trip(tip_amount=40.0),                                                  # R08 warning only
        trip(total_amount=-23.0),                                               # R04 negative total
    ]
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "yellow_tripdata_2025-01.parquet", rows)

    result = calidad.run_month(settings, JAN_2025)

    assert result.rows_read == 10
    assert result.rows_accepted == 3                     # good + passenger NULL + tip > fare
    assert result.rows_quarantined == 7
    assert result.rows_with_warnings == 2
    for rule in ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08", "R09"):
        assert result.violations[rule] == 1, rule

    quarantine = {row["violated_rules"] for row in _read(result.quarantine_file)}
    assert quarantine == {"R01", "R02", "R03", "R04", "R06", "R07", "R09"}
    duplicate = next(r for r in _read(result.quarantine_file) if r["violated_rules"] == "R07")
    assert duplicate["source_file"].endswith("yellow_tripdata_2025-01.parquet")
    assert duplicate["source_row_number"] == 3            # the second copy; the first stays accepted

    curated = _read(result.curated_file)
    assert sorted(r["quality_flags"] or "" for r in curated) == ["", "R05", "R08"]
    assert {r["year"] for r in curated} == {2025} and {r["month"] for r in curated} == {1}

    report = (settings.reports_dir / "quality" / "quality_report_2025-01.md").read_text(encoding="utf-8")
    assert "10 read = 3 accepted + 7 quarantined" in report
    assert (settings.reports_dir / "quality" / "quality_report_2025-01.csv").exists()


def test_cbd_fee_is_null_for_2024_and_does_not_trigger_r10(settings, zones_file):
    from src.config import Month

    jan_2024 = Month(2024, 1)
    columns = [c for c in __import__("tests.conftest", fromlist=["TLC_COLUMNS"]).TLC_COLUMNS if c != "cbd_congestion_fee"]
    rows = [trip(tpep_pickup_datetime=datetime(2024, 1, 10, 8, 0), tpep_dropoff_datetime=datetime(2024, 1, 10, 8, 20))]
    write_tlc_parquet(settings.raw_month_dir(jan_2024) / "yellow_tripdata_2024-01.parquet", rows, columns)

    result = calidad.run_month(settings, jan_2024)

    assert result.rows_accepted == 1 and result.violations["R10"] == 0
    assert _read(result.curated_file)[0]["cbd_congestion_fee"] is None
