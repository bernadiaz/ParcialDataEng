"""Schema contract: snake_case, aliases, missing/new columns and type differences."""
from __future__ import annotations

import duckdb
import pytest

from src import esquema
from src.config import configure_duckdb
from tests.conftest import JAN_2025, TLC_COLUMNS, trip, write_tlc_parquet


@pytest.mark.parametrize(
    "source, expected",
    [("PULocationID", "pu_location_id"), ("DOLocationID", "do_location_id"), ("VendorID", "vendor_id"),
     ("RatecodeID", "ratecode_id"), ("Airport_fee", "airport_fee"), ("tpep_pickup_datetime", "tpep_pickup_datetime"),
     ("LocationID", "location_id"), ("service_zone", "service_zone")],
)
def test_to_snake(source, expected):
    assert esquema.to_snake(source) == expected


def _register(settings, rows, columns=TLC_COLUMNS):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", rows, columns)
    con = configure_duckdb(duckdb.connect(), settings)
    report = esquema.register_yellow_month(con, settings, JAN_2025, esquema.load_contract(esquema.YELLOW_CONTRACT))
    return con, report


def test_contract_maps_every_tlc_column(settings):
    con, report = _register(settings, [trip()])
    assert report.status == "ok"
    assert report.mapping["PULocationID"] == "pu_location_id" and report.mapping["Airport_fee"] == "airport_fee"
    columns = [r[0] for r in con.execute("DESCRIBE yellow_src").fetchall()]
    assert columns[:3] == ["vendor_id", "tpep_pickup_datetime", "tpep_dropoff_datetime"]
    assert columns[-2:] == ["source_file", "source_row_number"]


def test_missing_optional_column_becomes_null(settings):
    columns = [c for c in TLC_COLUMNS if c != "cbd_congestion_fee"]
    con, report = _register(settings, [trip()], columns)
    assert report.missing_optional == ["cbd_congestion_fee"]
    assert con.execute("SELECT cbd_congestion_fee FROM yellow_src").fetchone()[0] is None


def test_missing_required_column_fails(settings):
    columns = [c for c in TLC_COLUMNS if c != "trip_distance"]
    with pytest.raises(esquema.SchemaError, match="trip_distance"):
        _register(settings, [trip()], columns)
    assert (settings.reports_dir / "schema" / "schema_report_yellow_2025-01.json").exists()


def test_new_column_is_ignored_with_a_warning(settings):
    rows = [trip() | {"surge_fee": 1.0}]
    con, report = _register(settings, rows, TLC_COLUMNS + ["surge_fee"])
    assert report.new_columns == ["surge_fee"] and report.status == "warning"
    assert "surge_fee" not in [r[0] for r in con.execute("DESCRIBE yellow_src").fetchall()]


def test_type_difference_is_cast_and_counted(settings, tmp_path):
    path = settings.raw_month_dir(JAN_2025) / "f.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = write_tlc_parquet(tmp_path / "typed.parquet", [trip(), trip()])
    con = duckdb.connect()
    # Airbyte-like file: passenger_count as text, one value not castable
    con.execute(
        f"""COPY (SELECT * REPLACE (CASE WHEN row_number() OVER () = 1 THEN 'two' ELSE CAST(passenger_count AS VARCHAR) END
                  AS passenger_count) FROM read_parquet('{rows.as_posix()}')) TO '{path.as_posix()}' (FORMAT PARQUET)"""
    )
    con2 = configure_duckdb(duckdb.connect(), settings)
    report = esquema.register_yellow_month(con2, settings, JAN_2025, esquema.load_contract(esquema.YELLOW_CONTRACT))
    assert report.type_mismatches["passenger_count"] == "VARCHAR -> BIGINT"
    assert report.cast_failures == {"passenger_count": 1}
