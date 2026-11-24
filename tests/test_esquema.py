"""Schema contract: snake_case, aliases, missing/new columns and type differences."""
from __future__ import annotations

import duckdb
import pytest

from src import esquema
from src.config import Month, configure_duckdb
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


# --- 2009-2010 files: other column names, text codes and coordinates instead of zone ids -----------------
LEGACY_2010 = Month(2010, 1)


def _spatial_or_skip() -> None:
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial")
        con.execute("LOAD spatial")
    except duckdb.Error as exc:  # pragma: no cover - offline machine without the extension cached
        pytest.skip(f"DuckDB spatial extension not available: {exc}")


def _write_zone_squares(settings) -> None:
    """Two square zones around Manhattan points: 2 (west) and 3 (east), in longitude/latitude."""
    target = settings.curated_zone_shapes_file
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("LOAD spatial")
    con.execute(
        f"""COPY (SELECT * FROM (VALUES
                (2, 'Jamaica Bay', 'Queens', ST_AsWKB(ST_GeomFromText('POLYGON((-74.00 40.70, -73.98 40.70, -73.98 40.72, -74.00 40.72, -74.00 40.70))'))),
                (3, 'Allerton/Pelham Gardens', 'Bronx', ST_AsWKB(ST_GeomFromText('POLYGON((-73.98 40.70, -73.96 40.70, -73.96 40.72, -73.98 40.72, -73.98 40.70))')))
            ) AS t(location_id, zone, borough, geom_wkb)) TO '{target.as_posix()}' (FORMAT PARQUET)""")


def test_2010_file_is_mapped_to_the_contract(settings):
    _spatial_or_skip()
    _write_zone_squares(settings)
    path = settings.raw_month_dir(LEGACY_2010) / "yellow_tripdata_2010-01.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        f"""COPY (SELECT * FROM (VALUES
              ('VTS', '2010-01-05 08:00:00', '2010-01-05 08:20:00', 1, 2.5, -73.99, 40.71, '1', '0', -73.97, 40.71, 'Cas', 9.7, 0.5, 0.5, 0.0, 0.0, 10.7),
              ('CMT', '2010-01-06 09:00:00', '2010-01-06 09:10:00', 2, 1.0, 0.0, 0.0, '1', '1', -73.50, 41.50, 'Cre', 5.3, 0.0, 0.5, 1.0, 0.0, 6.8),
              ('DDS', '2010-01-07 10:00:00', 'not a date', 1, 1.0, -73.97, 40.71, '1', NULL, -73.99, 40.71, 'No ', 4.1, 0.0, 0.5, 0.0, 0.0, 4.6)
            ) AS t(vendor_id, pickup_datetime, dropoff_datetime, passenger_count, trip_distance, pickup_longitude,
                   pickup_latitude, rate_code, store_and_fwd_flag, dropoff_longitude, dropoff_latitude, payment_type,
                   fare_amount, surcharge, mta_tax, tip_amount, tolls_amount, total_amount)
        ) TO '{path.as_posix()}' (FORMAT PARQUET)""")
    con.close()

    con = configure_duckdb(duckdb.connect(), settings)
    report = esquema.register_yellow_month(con, settings, LEGACY_2010, esquema.load_contract(esquema.YELLOW_CONTRACT))

    assert report.missing_required == [] and report.new_columns == []
    assert report.derived == {"pu_location_id": ["pickup_longitude", "pickup_latitude"],
                              "do_location_id": ["dropoff_longitude", "dropoff_latitude"]}
    assert set(report.missing_optional) == {"improvement_surcharge", "congestion_surcharge", "airport_fee", "cbd_congestion_fee"}
    assert set(report.value_mapped) == {"vendor_id", "payment_type"}
    assert report.cast_failures == {"vendor_id": 1, "tpep_dropoff_datetime": 1}  # DDS has no code; one bad date
    assert report.derived_unresolved == {"pu_location_id": {"unknown_264": 1, "outside_nyc_265": 0},
                                         "do_location_id": {"unknown_264": 0, "outside_nyc_265": 1}}
    rows = con.execute(
        "SELECT vendor_id, payment_type, pu_location_id, do_location_id, store_and_fwd_flag, extra, ratecode_id "
        "FROM yellow_src ORDER BY source_row_number").fetchall()
    assert rows == [(2, 2, 2, 3, "N", 0.5, 1), (1, 1, 264, 265, "Y", 0.0, 1), (None, 3, 3, 2, None, 0.0, 1)]
