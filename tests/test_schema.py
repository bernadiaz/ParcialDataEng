"""Tests de comparación de esquema y políticas de drift."""

from __future__ import annotations

from src.esquema import ColumnContract, compare_schema, load_contract


def _mini_contract() -> list[ColumnContract]:
    return [
        ColumnContract(
            name="vendor_id",
            type="BIGINT",
            required=True,
            nullable=True,
            source_aliases=["VendorID", "vendor_id"],
        ),
        ColumnContract(
            name="pu_location_id",
            type="BIGINT",
            required=True,
            nullable=False,
            source_aliases=["PULocationID", "pu_location_id"],
        ),
        ColumnContract(
            name="cbd_congestion_fee",
            type="DOUBLE",
            required=False,
            nullable=True,
            source_aliases=["cbd_congestion_fee"],
        ),
    ]


def test_load_contract_has_snake_case_destinations():
    cols = load_contract()
    names = {c.name for c in cols}
    assert "pu_location_id" in names
    assert "do_location_id" in names
    assert "VendorID" not in names


def test_missing_required_is_fatal():
    diff = compare_schema(
        source_file="x.parquet",
        year=2024,
        month=3,
        source_cols={"VendorID": "INTEGER"},
        contract=_mini_contract(),
        cbd_strategy="null",
    )
    assert not diff.ok
    assert "pu_location_id" in diff.missing_required
    assert any("pu_location_id" in f for f in diff.fatal)


def test_cbd_missing_becomes_null_warning_not_fatal():
    diff = compare_schema(
        source_file="yellow_2024.parquet",
        year=2024,
        month=3,
        source_cols={"VendorID": "INTEGER", "PULocationID": "INTEGER"},
        contract=_mini_contract(),
        cbd_strategy="null",
    )
    assert diff.ok
    assert "cbd_congestion_fee" in diff.missing_optional
    assert any("NULL" in w for w in diff.warnings)


def test_unexpected_column_ignored_with_warning():
    diff = compare_schema(
        source_file="yellow_2025.parquet",
        year=2025,
        month=3,
        source_cols={
            "VendorID": "INTEGER",
            "PULocationID": "INTEGER",
            "cbd_congestion_fee": "DOUBLE",
            "month": "VARCHAR",
            "year": "BIGINT",
        },
        contract=_mini_contract(),
        cbd_strategy="null",
    )
    assert diff.ok
    assert "month" in diff.unexpected
    assert "year" in diff.unexpected
    assert diff.mapped["vendor_id"] == "VendorID"
    assert diff.mapped["pu_location_id"] == "PULocationID"
