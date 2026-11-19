"""Part 3 - quality gate and quarantine (DuckDB).

Every row read ends in exactly one place:
  - curated     data/curated/yellow/year=YYYY/month=MM/part-0.parquet. Accepted rows, with the
                warning rule ids in quality_flags.
  - quarantine  data/quarantine/yellow/year=YYYY/month=MM/part-0.parquet. The row plus
                source_file, source_row_number and the reject rules it violated.
The run fails (exit code 1) when rows read != accepted + quarantined. Each month's partition is
written to a temporary folder and only replaces the previous one after the counts reconcile, so a
rerun replaces that month and nothing else.

    python -m src.calidad --mes 2025-01 --mes 2024-01
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import yaml

from src import esquema
from src.config import (
    CONTRACTS_DIR,
    RUN_ID,
    Month,
    Settings,
    configure_duckdb,
    control_db,
    duckdb_config,
    get_logger,
    track_step,
)
from src.observability import push

log = get_logger("calidad")
RULES_PATH = CONTRACTS_DIR / "quality_rules.yaml"
PART_FILE = "part-0.parquet"


class ReconciliationError(RuntimeError):
    """rows read != rows accepted + rows quarantined."""


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    description: str
    threshold: str
    rationale: str
    predicate: str

    def condition(self, values: dict[str, Any]) -> str:
        # COALESCE: a NULL predicate is "not violated"; predicates handle NULLs explicitly.
        return f"COALESCE(({self.predicate.format(**values)}), FALSE)"


def load_rules(path: Path = RULES_PATH) -> tuple[dict[str, Any], list[Rule]]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = [
        Rule(
            id=r["id"], name=r["name"], severity=r["severity"], description=r["description"],
            threshold=str(r["threshold"]), rationale=" ".join(str(r["rationale"]).split()), predicate=r["predicate"],
        )
        for r in spec["rules"]
    ]
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("quality_rules.yaml: duplicated rule ids")
    if bad := [r.id for r in rules if r.severity not in {"reject", "warning"}]:
        raise ValueError(f"quality_rules.yaml: invalid severity in {bad}")
    if len(rules) < 8:
        raise ValueError("quality_rules.yaml: the exam requires at least 8 rules")
    return spec.get("parameters", {}), rules


def reconcile(rows_read: int, rows_accepted: int, rows_quarantined: int, mes: str = "") -> None:
    """Invariant checked on every run: every row read is either accepted or quarantined."""
    if rows_read != rows_accepted + rows_quarantined:
        raise ReconciliationError(
            f"{mes}: rows read ({rows_read:,}) != accepted ({rows_accepted:,}) + quarantined ({rows_quarantined:,})"
        )


@dataclass
class QualityResult:
    mes: str
    rows_read: int
    rows_accepted: int
    rows_quarantined: int
    rows_with_warnings: int
    violations: dict[str, int] = field(default_factory=dict)
    curated_file: Path | None = None
    quarantine_file: Path | None = None


def _flags(rules: list[Rule], values: dict[str, Any]) -> str:
    if not rules:
        return "CAST([] AS VARCHAR[])"
    cases = ", ".join(f"CASE WHEN {r.condition(values)} THEN '{r.id}' END" for r in rules)
    return f"list_filter([{cases}], lambda x: x IS NOT NULL)"


def _swap_in(tmp_dir: Path, final_dir: Path) -> None:
    """Replaces one partition folder with the freshly written one."""
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir.rename(final_dir)


def run_month(
    settings: Settings,
    month: Month,
    *,
    con: duckdb.DuckDBPyConnection | None = None,
    contract: dict[str, Any] | None = None,
    zone_contract: dict[str, Any] | None = None,
    rules_spec: tuple[dict[str, Any], list[Rule]] | None = None,
) -> QualityResult:
    contract = contract or esquema.load_contract(esquema.YELLOW_CONTRACT)
    zone_contract = zone_contract or esquema.load_contract(esquema.ZONES_CONTRACT)
    params, rules = rules_spec or load_rules()
    con = con or configure_duckdb(duckdb.connect(), settings)

    esquema.register_zones(con, settings, zone_contract)
    esquema.write_curated_zones(con, settings)
    esquema.register_yellow_month(con, settings, month, contract)

    values = {**params, "year": month.year, "month": month.month}
    columns = [c["name"] for c in contract["columns"]]
    rejects = [r for r in rules if r.severity == "reject"]
    warnings = [r for r in rules if r.severity == "warning"]

    con.execute(
        f"""CREATE OR REPLACE TEMP TABLE checked AS
        WITH base AS (
            SELECT s.*,
                   date_diff('second', s.tpep_pickup_datetime, s.tpep_dropoff_datetime) AS duration_sec,
                   pz.location_id IS NOT NULL AS pu_zone_exists,
                   dz.location_id IS NOT NULL AS do_zone_exists,
                   row_number() OVER (
                       PARTITION BY {', '.join(f's.{c}' for c in columns)}
                       ORDER BY s.source_file, s.source_row_number
                   ) AS dup_rank
            FROM yellow_src s
            LEFT JOIN zones pz ON s.pu_location_id = pz.location_id
            LEFT JOIN zones dz ON s.do_location_id = dz.location_id
        )
        SELECT *, {_flags(rejects, values)} AS reject_rules, {_flags(warnings, values)} AS warning_rules
        FROM base"""
    )
    rows_read = con.execute("SELECT count(*) FROM checked").fetchone()[0]

    curated_dir = settings.curated_month_dir(month)
    quarantine_dir = settings.quarantine_month_dir(month)
    tmp_curated = curated_dir.with_name(curated_dir.name + ".tmp")
    tmp_quarantine = quarantine_dir.with_name(quarantine_dir.name + ".tmp")
    for tmp in (tmp_curated, tmp_quarantine):
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)

    select_cols = ", ".join(columns)
    partition_cols = f"CAST({month.year} AS SMALLINT) AS year, CAST({month.month} AS SMALLINT) AS month, '{RUN_ID}' AS run_id"
    con.execute(
        f"""COPY (
            SELECT {select_cols}, source_file, source_row_number,
                   NULLIF(array_to_string(warning_rules, ';'), '') AS quality_flags,
                   {partition_cols}
            FROM checked WHERE len(reject_rules) = 0
        ) TO '{(tmp_curated / PART_FILE).as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"""
    )
    con.execute(
        f"""COPY (
            SELECT {select_cols}, source_file, source_row_number,
                   array_to_string(reject_rules, ';') AS violated_rules,
                   NULLIF(array_to_string(warning_rules, ';'), '') AS warning_flags,
                   {partition_cols}, now() AS quarantined_at
            FROM checked WHERE len(reject_rules) > 0
        ) TO '{(tmp_quarantine / PART_FILE).as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"""
    )

    # Reconcile on what was actually written, before publishing the partition.
    rows_accepted = con.execute(f"SELECT count(*) FROM read_parquet('{(tmp_curated / PART_FILE).as_posix()}')").fetchone()[0]
    rows_quarantined = con.execute(f"SELECT count(*) FROM read_parquet('{(tmp_quarantine / PART_FILE).as_posix()}')").fetchone()[0]
    reconcile(rows_read, rows_accepted, rows_quarantined, month.label)

    violations = dict(
        con.execute(
            "SELECT rule_id, count(*) FROM (SELECT unnest(list_concat(reject_rules, warning_rules)) AS rule_id FROM checked) GROUP BY 1"
        ).fetchall()
    )
    rows_with_warnings = con.execute(
        "SELECT count(*) FROM checked WHERE len(reject_rules) = 0 AND len(warning_rules) > 0"
    ).fetchone()[0]
    con.execute("DROP TABLE checked")

    _swap_in(tmp_curated, curated_dir)
    _swap_in(tmp_quarantine, quarantine_dir)

    result = QualityResult(
        mes=month.label,
        rows_read=rows_read,
        rows_accepted=rows_accepted,
        rows_quarantined=rows_quarantined,
        rows_with_warnings=rows_with_warnings,
        violations={r.id: int(violations.get(r.id, 0)) for r in rules},
        curated_file=curated_dir / PART_FILE,
        quarantine_file=quarantine_dir / PART_FILE,
    )
    write_reports(settings, result, rules, values)
    push_quality_metrics(result, rules)
    log.info(
        "quality %s: read=%s accepted=%s quarantined=%s warnings=%s reconciled=yes",
        month, f"{rows_read:,}", f"{rows_accepted:,}", f"{rows_quarantined:,}", f"{rows_with_warnings:,}",
    )
    return result


def push_quality_metrics(result: QualityResult, rules: list[Rule]) -> None:
    """Rows per outcome and violations per rule -> Pushgateway -> Prometheus -> Grafana."""
    samples = [
        ("nyc_taxi_rows", "Rows per quality outcome", {"outcome": outcome}, float(value))
        for outcome, value in (
            ("read", result.rows_read), ("accepted", result.rows_accepted),
            ("quarantined", result.rows_quarantined), ("accepted_with_warnings", result.rows_with_warnings),
        )
    ]
    samples += [
        ("nyc_taxi_rule_violations", "Rows violating each quality rule", {"rule": r.id, "severity": r.severity},
         float(result.violations.get(r.id, 0)))
        for r in rules
    ]
    samples.append(("nyc_taxi_reconciled", "1 if rows read = accepted + quarantined", {}, 1.0))
    push("quality", result.mes, samples)


def write_reports(settings: Settings, result: QualityResult, rules: list[Rule], values: dict[str, Any]) -> tuple[Path, Path]:
    """quality_report_<mes>.md and .csv, plus rows in the control database (one set per month)."""
    out_dir = settings.reports_dir / "quality"
    out_dir.mkdir(parents=True, exist_ok=True)
    read = result.rows_read or 1
    rows = [
        {
            "mes": result.mes,
            "rule_id": r.id,
            "name": r.name,
            "severity": r.severity,
            "threshold": r.threshold.format(**values),
            "violations": result.violations.get(r.id, 0),
            "pct_of_read": round(100 * result.violations.get(r.id, 0) / read, 4),
            "description": r.description,
        }
        for r in rules
    ]
    csv_path = out_dir / f"quality_report_{result.mes}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = [
        f"# Quality report - {result.mes}",
        "",
        f"Run `{RUN_ID}`. A row can violate several rules, so rule counts do not add up to the quarantine.",
        "",
        "| metric | rows | % of read |",
        "|---|---:|---:|",
        f"| read | {result.rows_read:,} | 100.00 |",
        f"| accepted (curated) | {result.rows_accepted:,} | {100 * result.rows_accepted / read:.2f} |",
        f"| quarantined | {result.rows_quarantined:,} | {100 * result.rows_quarantined / read:.2f} |",
        f"| accepted with warnings | {result.rows_with_warnings:,} | {100 * result.rows_with_warnings / read:.2f} |",
        "",
        f"Reconciliation: {result.rows_read:,} read = {result.rows_accepted:,} accepted + {result.rows_quarantined:,} quarantined.",
        "",
        "| rule | severity | description | threshold | rows | % of read |",
        "|---|---|---|---|---:|---:|",
        *[
            f"| {r['rule_id']} | {r['severity']} | {r['description']} | {r['threshold']} | {r['violations']:,} | {r['pct_of_read']:.4f} |"
            for r in rows
        ],
        "",
    ]
    md_path = out_dir / f"quality_report_{result.mes}.md"
    md_path.write_text("\n".join(summary), encoding="utf-8")

    with control_db(settings) as con:
        con.execute("DELETE FROM quality_summary WHERE mes = ? AND run_id = ?", [result.mes, RUN_ID])
        con.execute("DELETE FROM quality_report WHERE mes = ? AND run_id = ?", [result.mes, RUN_ID])
        con.execute(
            "INSERT INTO quality_summary VALUES (?, ?, ?, ?, ?, ?, TRUE, now())",
            [RUN_ID, result.mes, result.rows_read, result.rows_accepted, result.rows_quarantined, result.rows_with_warnings],
        )
        con.executemany(
            "INSERT INTO quality_report VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())",
            [[RUN_ID, r["mes"], r["rule_id"], r["name"], r["severity"], r["threshold"], r["violations"], r["pct_of_read"]] for r in rows],
        )
    return md_path, csv_path


# --- quarantine files -------------------------------------------------------------------------------------
def quarantine_file(settings: Settings, month: Month) -> Path:
    return settings.quarantine_month_dir(month) / PART_FILE


def quarantine_by_rule(settings: Settings, month: Month) -> dict[str, int]:
    """Quarantined rows per violated reject rule (a row can violate several, so they overlap)."""
    path = quarantine_file(settings, month)
    if not path.exists():
        return {}
    with duckdb.connect(config=duckdb_config()) as con:
        rows = con.execute(
            "SELECT rule_id, count(*) FROM (SELECT unnest(string_split(violated_rules, ';')) AS rule_id "
            f"FROM read_parquet('{path.as_posix()}', hive_partitioning = false)) GROUP BY 1 ORDER BY 1"
        ).fetchall()
    return {rule: int(n) for rule, n in rows}


def publish_quarantine(settings: Settings, month: Month, s3: Any | None = None) -> str | None:
    """Cloud mode: copies the month's quarantine file to the lake, next to the raw zone:
    s3://<bucket>/<S3_QUARANTINE_PREFIX>/yellow/year=YYYY/month=MM/part-0.parquet. Any other object of
    that month's prefix is removed, so a rerun replaces the month. Offline mode (or no bucket): None."""
    if not settings.s3_bucket or settings.offline:
        return None
    path = quarantine_file(settings, month)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run `make quality MES={month}` first")
    if s3 is None:
        from src.ingesta_airbyte import S3Store

        s3 = S3Store(settings)
    prefix = f"{settings.s3_quarantine_prefix}/yellow/{month.partition}/"
    key = prefix + PART_FILE
    s3.upload(path, key)
    stale = [o["key"] for o in s3.list(prefix) if o["key"] != key]
    if stale:
        s3.delete(stale)
    log.info("quarantine %s: %s", month, s3.uri(key))
    return s3.uri(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", action="append", required=True, help="YYYY-MM (repeatable)")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    contract = esquema.load_contract(esquema.YELLOW_CONTRACT)
    zone_contract = esquema.load_contract(esquema.ZONES_CONTRACT)
    rules_spec = load_rules()
    try:
        for value in args.mes:
            month = Month.parse(value)
            with track_step(settings, "quality", month.label):
                run_month(settings, month, contract=contract, zone_contract=zone_contract, rules_spec=rules_spec)
    except (ReconciliationError, esquema.SchemaError) as exc:
        log.error("%s", exc)
        if isinstance(exc, ReconciliationError):
            push("quality", month.label, [("nyc_taxi_reconciled", "1 if rows read = accepted + quarantined", {}, 0.0)],
                 replace=False)  # keep the failed step status pushed by track_step
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
