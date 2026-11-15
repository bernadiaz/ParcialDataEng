"""Part 2 - schema contract.

Before anything is loaded, each raw file is compared with its versioned contract
(contracts/yellow_schema.yaml, contracts/taxi_zone_schema.yaml). The check reports missing
columns, new columns and different types. Names are normalized to snake_case, and both months
become the same typed relation (cbd_congestion_fee is NULL in 2024).

    python -m src.esquema --mes 2025-01 --mes 2024-01
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

from src.config import (
    CONTRACTS_DIR,
    RUN_ID,
    Month,
    Settings,
    configure_duckdb,
    control_db,
    get_logger,
    track_step,
)

log = get_logger("esquema")

YELLOW_CONTRACT = CONTRACTS_DIR / "yellow_schema.yaml"
ZONES_CONTRACT = CONTRACTS_DIR / "taxi_zone_schema.yaml"
READER_COLUMNS = {"filename", "file_row_number"}  # added by DuckDB's readers, not by the source


class SchemaError(RuntimeError):
    """A file cannot satisfy its contract (missing required column, duplicate key...)."""


def to_snake(name: str) -> str:
    """PULocationID -> pu_location_id, VendorID -> vendor_id, Airport_fee -> airport_fee."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name.strip())
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def load_contract(path: Path) -> dict[str, Any]:
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    names = [column["name"] for column in contract["columns"]]
    if len(names) != len(set(names)):
        raise SchemaError(f"{path.name}: duplicated column names in the contract")
    return contract


@dataclass
class SchemaReport:
    dataset: str
    mes: str
    files: list[str]
    mapping: dict[str, str] = field(default_factory=dict)  # source column -> contract column
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)  # filled with NULL
    new_columns: list[str] = field(default_factory=list)  # not in the contract: ignored + warning
    ignored_metadata: list[str] = field(default_factory=list)  # _airbyte_* columns
    type_mismatches: dict[str, str] = field(default_factory=dict)
    cast_failures: dict[str, int] = field(default_factory=dict)
    null_violations: dict[str, int] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.missing_required:
            return "fail"
        if self.new_columns or self.type_mismatches or self.cast_failures or self.null_violations:
            return "warning"
        return "ok"


def _describe(con: duckdb.DuckDBPyConnection, relation: str) -> dict[str, str]:
    return {row[0]: row[1] for row in con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()}


def _resolve(source_types: dict[str, str], contract: dict[str, Any], report: SchemaReport) -> None:
    """Maps every source column to a contract column (aliases first, then snake_case)."""
    lookup: dict[str, str] = {}
    for column in contract["columns"]:
        lookup[column["name"]] = column["name"]
        for alias in column.get("source_aliases", []):
            lookup[alias] = column["name"]
    prefixes = tuple(contract.get("ignored_column_prefixes", []))

    for source in source_types:
        if source in READER_COLUMNS:
            continue
        if prefixes and source.startswith(prefixes):
            report.ignored_metadata.append(source)
            continue
        target = lookup.get(source) or lookup.get(to_snake(source))
        if target is None:
            report.new_columns.append(source)
            continue
        if target in report.mapping.values():
            raise SchemaError(f"{report.dataset} {report.mes}: two source columns map to {target!r}")
        report.mapping[source] = target

    mapped = set(report.mapping.values())
    by_name = {column["name"]: column for column in contract["columns"]}
    for name, column in by_name.items():
        if name not in mapped:
            target_list = report.missing_required if column.get("required", True) else report.missing_optional
            target_list.append(name)
    for source, target in report.mapping.items():
        expected = by_name[target]["type"].upper()
        actual = source_types[source].upper()
        if actual != expected:
            report.type_mismatches[target] = f"{actual} -> {expected}"


def _select_list(contract: dict[str, Any], report: SchemaReport) -> list[str]:
    inverse = {target: source for source, target in report.mapping.items()}
    columns = []
    for column in contract["columns"]:
        name, kind = column["name"], column["type"]
        source = inverse.get(name)
        columns.append(f'TRY_CAST("{source}" AS {kind}) AS {name}' if source else f"CAST(NULL AS {kind}) AS {name}")
    return columns


def _profile(con: duckdb.DuckDBPyConnection, relation: str, view: str, contract: dict[str, Any], report: SchemaReport) -> None:
    """Counts values lost by TRY_CAST and NULLs in non-nullable columns (one scan each)."""
    inverse = {target: source for source, target in report.mapping.items()}
    by_name = {column["name"]: column for column in contract["columns"]}
    if report.type_mismatches:
        parts = [
            f'count(*) FILTER (WHERE "{inverse[target]}" IS NOT NULL '
            f'AND TRY_CAST("{inverse[target]}" AS {by_name[target]["type"]}) IS NULL)'
            for target in report.type_mismatches
        ]
        values = con.execute(f"SELECT {', '.join(parts)} FROM {relation}").fetchone()
        report.cast_failures = {t: int(v) for t, v in zip(report.type_mismatches, values) if v}
    not_nullable = [c["name"] for c in contract["columns"] if not c.get("nullable", True) and c["name"] in inverse]
    if not_nullable:
        parts = [f"count(*) FILTER (WHERE {name} IS NULL)" for name in not_nullable]
        values = con.execute(f"SELECT {', '.join(parts)} FROM {view}").fetchone()
        report.null_violations = {n: int(v) for n, v in zip(not_nullable, values) if v}


def _file_list(files: list[Path]) -> str:
    return "[" + ", ".join(f"'{path.as_posix()}'" for path in files) + "]"


def register_yellow_month(
    con: duckdb.DuckDBPyConnection, settings: Settings, month: Month, contract: dict[str, Any]
) -> SchemaReport:
    """Creates the temp view `yellow_src`: contract columns (snake_case, contract types) plus
    source_file and source_row_number, which point back to the untouched raw row."""
    files = sorted(settings.raw_month_dir(month).rglob("*.parquet"))
    if not files:
        raise SchemaError(f"No raw Parquet files for {month} in {settings.raw_month_dir(month)}: run `make airbyte-sync` first")
    # hive_partitioning = false: year=/month= folders are our layout, not columns of the TLC file.
    relation = (
        f"read_parquet({_file_list(files)}, filename = true, file_row_number = true, "
        "union_by_name = true, hive_partitioning = false)"
    )
    report = SchemaReport(dataset="yellow", mes=month.label, files=[settings.relative(p) for p in files])
    _resolve(_describe(con, relation), contract, report)
    if report.missing_required:
        _persist(settings, report)
        raise SchemaError(f"yellow {month}: missing required columns {report.missing_required}")

    data_root = settings.data_dir.as_posix().rstrip("/") + "/"
    con.execute(
        f"""CREATE OR REPLACE TEMP VIEW yellow_src AS
            SELECT {', '.join(_select_list(contract, report))},
                   replace(filename, '{data_root}', '') AS source_file,
                   file_row_number AS source_row_number
            FROM {relation}"""
    )
    _profile(con, relation, "yellow_src", contract, report)
    _persist(settings, report)
    return report


def register_zones(con: duckdb.DuckDBPyConnection, settings: Settings, contract: dict[str, Any]) -> SchemaReport:
    """Creates the temp view `zones` from the raw lookup (CSV from the TLC or Airbyte, or Parquet)."""
    # Plain CSV from the TLC, or gzip-compressed CSV written by Airbyte's S3 destination (0.csv.gz).
    csv_files = sorted([*settings.raw_zones_dir.rglob("*.csv"), *settings.raw_zones_dir.rglob("*.csv.gz")])
    parquet_files = sorted(settings.raw_zones_dir.rglob("*.parquet"))
    if csv_files:
        relation = f"read_csv({_file_list(csv_files)}, header = true, all_varchar = true, union_by_name = true)"
        files = csv_files
    elif parquet_files:
        relation = f"read_parquet({_file_list(parquet_files)}, union_by_name = true, hive_partitioning = false)"
        files = parquet_files
    else:
        raise SchemaError(f"No taxi zone lookup in {settings.raw_zones_dir}: run `make airbyte-sync` first")

    report = SchemaReport(dataset="zones", mes="static", files=[settings.relative(p) for p in files])
    source_types = _describe(con, relation)
    _resolve(source_types, contract, report)
    if csv_files:  # every CSV column is read as VARCHAR on purpose; only real cast failures matter
        report.type_mismatches = {}
    if report.missing_required:
        _persist(settings, report)
        raise SchemaError(f"zones: missing required columns {report.missing_required}")
    con.execute(f"CREATE OR REPLACE TEMP VIEW zones AS SELECT {', '.join(_select_list(contract, report))} FROM {relation}")

    keys = contract.get("primary_key", [])
    if keys:
        duplicates = con.execute(
            f"SELECT count(*) FROM (SELECT {', '.join(keys)} FROM zones GROUP BY ALL HAVING count(*) > 1)"
        ).fetchone()[0]
        if duplicates:
            raise SchemaError(f"zones: {duplicates} duplicated {keys} values; R06 and the enrichment join need a unique key")
        null_keys = con.execute(f"SELECT count(*) FROM zones WHERE {' OR '.join(f'{k} IS NULL' for k in keys)}").fetchone()[0]
        if null_keys:
            raise SchemaError(f"zones: {null_keys} rows with NULL {keys}")
    _persist(settings, report)
    return report


def write_curated_zones(con: duckdb.DuckDBPyConnection, settings: Settings) -> Path:
    """Normalized zone lookup, loaded to the warehouse next to the trips."""
    target = settings.curated_zones_file
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.parquet")
    con.execute(f"COPY (SELECT * FROM zones ORDER BY location_id) TO '{tmp.as_posix()}' (FORMAT PARQUET)")
    tmp.replace(target)
    return target


def _persist(settings: Settings, report: SchemaReport) -> None:
    """schema_report_<mes>.md/.json in data/reports/schema and a row in control.schema_report."""
    out_dir = settings.reports_dir / "schema"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"schema_report_{report.dataset}_{report.mes}"
    payload = asdict(report) | {"status": report.status, "run_id": RUN_ID}
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def bullet(values: Any) -> str:
        if not values:
            return "none"
        if isinstance(values, dict):
            return ", ".join(f"`{k}` ({v})" for k, v in values.items())
        return ", ".join(f"`{v}`" for v in values)

    lines = [
        f"# Schema report - {report.dataset} {report.mes}",
        "",
        f"- Status: **{report.status}** (run `{RUN_ID}`)",
        f"- Files: {bullet(report.files)}",
        f"- Missing required columns (fail): {bullet(report.missing_required)}",
        f"- Missing optional columns (filled with NULL): {bullet(report.missing_optional)}",
        f"- New columns not in the contract (ignored, warning): {bullet(report.new_columns)}",
        f"- Airbyte metadata columns (ignored): {bullet(report.ignored_metadata)}",
        f"- Type differences (TRY_CAST to the contract type): {bullet(report.type_mismatches)}",
        f"- Values that could not be cast (became NULL): {bullet(report.cast_failures)}",
        f"- NULLs in non-nullable columns (handled by the quality rules): {bullet(report.null_violations)}",
        "",
        "| source column | contract column |",
        "|---|---|",
        *[f"| `{s}` | `{t}` |" for s, t in report.mapping.items()],
        "",
    ]
    (out_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")

    with control_db(settings) as con:
        con.execute("DELETE FROM schema_report WHERE dataset = ? AND mes = ? AND run_id = ?", [report.dataset, report.mes, RUN_ID])
        con.execute(
            "INSERT INTO schema_report VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())",
            [
                RUN_ID,
                report.dataset,
                report.mes,
                json.dumps(report.files),
                json.dumps(report.missing_required),
                json.dumps(report.missing_optional),
                json.dumps(report.new_columns),
                json.dumps(report.type_mismatches),
                json.dumps(report.cast_failures),
                json.dumps(report.null_violations),
                report.status,
            ],
        )
    level = log.warning if report.status != "ok" else log.info
    level(
        "schema %s %s: status=%s new=%s missing_optional=%s type_diffs=%s cast_failures=%s",
        report.dataset, report.mes, report.status, report.new_columns, report.missing_optional,
        report.type_mismatches, report.cast_failures,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", action="append", required=True, help="YYYY-MM (repeatable)")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    yellow = load_contract(YELLOW_CONTRACT)
    zones = load_contract(ZONES_CONTRACT)
    try:
        with track_step(settings, "schema", ",".join(args.mes)):
            con = configure_duckdb(duckdb.connect(), settings)
            register_zones(con, settings, zones)
            for value in args.mes:
                register_yellow_month(con, settings, Month.parse(value), yellow)
    except SchemaError as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
