"""Parte 3 — Calidad, cuarentena, flags de advertencia y reconciliación.

Lee staging Hive, aplica reglas de `contracts/quality_rules.yaml`,
escribe aceptadas + cuarentena y falla si no reconcilia conteos.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.config import ROOT, Settings, get_settings
from src.duck import connect
from src.esquema import staging_path
from src.ingesta_airbyte import MonthRef, comparison_month, local_zones_path, parse_mes

RULES_PATH = ROOT / "contracts" / "quality_rules.yaml"

# Columnas de negocio para hash de duplicados (sin linaje).
BUSINESS_COLS = [
    "vendor_id",
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "passenger_count",
    "trip_distance",
    "ratecode_id",
    "store_and_fwd_flag",
    "pu_location_id",
    "do_location_id",
    "payment_type",
    "fare_amount",
    "extra",
    "mta_tax",
    "tip_amount",
    "tolls_amount",
    "improvement_surcharge",
    "total_amount",
    "congestion_surcharge",
    "airport_fee",
    "cbd_congestion_fee",
]


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    severity: str
    description: str


def load_rules(path: Path = RULES_PATH) -> list[Rule]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        Rule(
            id=r["id"],
            name=r["name"],
            severity=r["severity"],
            description=r["description"].strip(),
        )
        for r in raw["rules"]
    ]


def accepted_path(settings: Settings, ref: MonthRef) -> Path:
    return (
        settings.data_dir
        / "accepted"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / "part.parquet"
    )


def quarantine_path(settings: Settings, ref: MonthRef) -> Path:
    return (
        settings.data_dir
        / "quarantine"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / "part.parquet"
    )


def _hash_expr() -> str:
    cols = ", ".join(BUSINESS_COLS)
    return f"hash({cols})"


def _rule_expressions(max_distance: float) -> dict[str, str]:
    """Expresiones booleanas SQL por regla (sobre alias `t` y joins de zona)."""
    return {
        "R01": (
            "year(t.tpep_pickup_datetime) != t.source_year "
            "OR month(t.tpep_pickup_datetime) != t.source_month"
        ),
        "R02": "t.tpep_dropoff_datetime <= t.tpep_pickup_datetime",
        "R03": (
            f"t.trip_distance IS NULL OR t.trip_distance <= 0 "
            f"OR t.trip_distance > {max_distance}"
        ),
        "R04": "t.total_amount IS NULL OR t.total_amount < 0",
        "R05": "t.passenger_count IS NULL OR t.passenger_count = 0",
        "R06": "zpu.LocationID IS NULL OR zdo.LocationID IS NULL",
        "R07": "dup.cnt > 1",
        "R08": (
            "t.tip_amount < 0 OR "
            "(t.fare_amount > 0 AND t.tip_amount > t.fare_amount)"
        ),
        "R09": (
            "date_diff('minute', t.tpep_pickup_datetime, t.tpep_dropoff_datetime) > 480"
        ),
    }


def process_month(
    *,
    con,
    settings: Settings,
    ref: MonthRef,
    rules: list[Rule],
) -> dict[str, Any]:
    stg = staging_path(settings, ref)
    if not stg.exists():
        raise FileNotFoundError(
            f"Falta staging {stg}. Corré `make schema` antes."
        )
    zones = local_zones_path(settings)
    if not zones.exists():
        raise FileNotFoundError(f"Falta zonas {zones}. Corré `make ingest` antes.")

    max_dist = settings.max_distance_miles
    exprs = _rule_expressions(max_dist)
    reject_ids = [r.id for r in rules if r.severity == "reject"]
    warn_ids = [r.id for r in rules if r.severity == "warn"]

    # Tablas temporales por mes (liberar memoria entre meses)
    con.execute("DROP TABLE IF EXISTS q_src")
    con.execute("DROP TABLE IF EXISTS q_dup")
    con.execute("DROP TABLE IF EXISTS q_flagged")

    stg_sql = str(stg).replace("'", "''")
    zones_sql = str(zones).replace("'", "''")

    con.execute(
        f"CREATE TEMP TABLE q_src AS SELECT * FROM read_parquet('{stg_sql}')"
    )
    n_read = con.execute("SELECT count(*) FROM q_src").fetchone()[0]

    con.execute(
        f"""
        CREATE TEMP TABLE q_dup AS
        SELECT {_hash_expr()} AS row_hash, count(*)::BIGINT AS cnt
        FROM q_src
        GROUP BY 1
        """
    )

    flag_selects = []
    for rid, expr in exprs.items():
        flag_selects.append(f"({expr}) AS {rid.lower()}")
    flags_sql = ",\n          ".join(flag_selects)

    con.execute(
        f"""
        CREATE TEMP TABLE q_flagged AS
        SELECT
          t.*,
          {_hash_expr()} AS row_hash,
          {flags_sql}
        FROM q_src t
        LEFT JOIN q_dup dup ON {_hash_expr()} = dup.row_hash
        LEFT JOIN read_csv_auto('{zones_sql}') zpu
          ON t.pu_location_id = zpu.LocationID
        LEFT JOIN read_csv_auto('{zones_sql}') zdo
          ON t.do_location_id = zdo.LocationID
        """
    )

    # Listas de reglas violadas
    reject_list_expr = " || ".join(
        [
            f"CASE WHEN {rid.lower()} THEN '{rid}|' ELSE '' END"
            for rid in reject_ids
        ]
    )
    warn_list_expr = " || ".join(
        [
            f"CASE WHEN {rid.lower()} THEN '{rid}|' ELSE '' END"
            for rid in warn_ids
        ]
    )
    any_reject = " OR ".join(f"{rid.lower()}" for rid in reject_ids)

    # Conteos por regla
    per_rule: dict[str, int] = {}
    for r in rules:
        per_rule[r.id] = con.execute(
            f"SELECT count(*) FROM q_flagged WHERE {r.id.lower()}"
        ).fetchone()[0]

    n_reject = con.execute(
        f"SELECT count(*) FROM q_flagged WHERE {any_reject}"
    ).fetchone()[0]
    n_accepted = n_read - n_reject

    # Paths salida (reemplazo de partición del mes)
    acc = accepted_path(settings, ref)
    qua = quarantine_path(settings, ref)
    acc.parent.mkdir(parents=True, exist_ok=True)
    qua.parent.mkdir(parents=True, exist_ok=True)
    if acc.exists():
        acc.unlink()
    if qua.exists():
        qua.unlink()

    # Columnas base = staging (sin flags booleanas auxiliares)
    base_cols = con.execute("DESCRIBE SELECT * FROM q_src").fetchall()
    base_names = [c[0] for c in base_cols]
    # Evitar colisiones con particiones hive al leer después
    base_names = [c for c in base_names if c not in {"year", "month"}]
    proj = ", ".join(f"q.{c}" for c in base_names)

    acc_sql = str(acc).replace("'", "''")
    qua_sql = str(qua).replace("'", "''")

    con.execute(
        f"""
        COPY (
          SELECT {proj},
            rtrim(
              CASE WHEN length({warn_list_expr}) > 0
                   THEN {warn_list_expr} ELSE '' END,
              '|'
            ) AS quality_flags
          FROM q_flagged q
          WHERE NOT ({any_reject})
        ) TO '{acc_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    con.execute(
        f"""
        COPY (
          SELECT {proj},
            rtrim(
              CASE WHEN length({reject_list_expr}) > 0
                   THEN {reject_list_expr} ELSE '' END,
              '|'
            ) AS violated_rules,
            rtrim(
              CASE WHEN length({warn_list_expr}) > 0
                   THEN {warn_list_expr} ELSE '' END,
              '|'
            ) AS quality_flags
          FROM q_flagged q
          WHERE {any_reject}
        ) TO '{qua_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    n_acc_file = (
        con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{acc_sql}')"
        ).fetchone()[0]
        if acc.exists() and acc.stat().st_size > 0
        else 0
    )
    n_qua_file = (
        con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{qua_sql}')"
        ).fetchone()[0]
        if qua.exists() and qua.stat().st_size > 0
        else 0
    )

    # Si no hay cuarentena, crear parquet vacío con esquema mínimo es complicado;
    # dejamos archivo solo si hay filas. Para reconciliación usamos conteos SQL.
    if n_reject == 0 and qua.exists():
        qua.unlink()

    reconciled = n_read == n_accepted + n_reject == n_acc_file + n_qua_file

    summary = {
        "mes": ref.label,
        "source_file": stg.name,
        "rows_read": int(n_read),
        "rows_accepted": int(n_accepted),
        "rows_quarantine": int(n_reject),
        "rows_accepted_file": int(n_acc_file),
        "rows_quarantine_file": int(n_qua_file),
        "reconciled": bool(reconciled),
        "per_rule": per_rule,
        "max_distance_miles": max_dist,
        "accepted_path": str(acc.relative_to(settings.data_dir)),
        "quarantine_path": str(qua.relative_to(settings.data_dir))
        if qua.exists()
        else None,
    }

    con.execute("DROP TABLE IF EXISTS q_flagged")
    con.execute("DROP TABLE IF EXISTS q_dup")
    con.execute("DROP TABLE IF EXISTS q_src")

    return summary


def write_quality_reports(
    settings: Settings,
    mes: str,
    rules: list[Rule],
    summaries: list[dict[str, Any]],
) -> Path:
    reports = settings.data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    base = reports / f"quality_report_{mes}"

    base.with_suffix(".json").write_text(
        json.dumps({"rules": [r.__dict__ for r in rules], "months": summaries}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    # CSV largo: una fila por mes-regla + totales
    csv_path = base.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "mes",
                "rows_read",
                "rows_accepted",
                "rows_quarantine",
                "reconciled",
                "rule_id",
                "rule_count",
                "severity",
            ],
        )
        w.writeheader()
        for s in summaries:
            for r in rules:
                w.writerow(
                    {
                        "mes": s["mes"],
                        "rows_read": s["rows_read"],
                        "rows_accepted": s["rows_accepted"],
                        "rows_quarantine": s["rows_quarantine"],
                        "reconciled": s["reconciled"],
                        "rule_id": r.id,
                        "rule_count": s["per_rule"].get(r.id, 0),
                        "severity": r.severity,
                    }
                )

    lines = [
        f"# Quality report — MES={mes}",
        "",
        f"Reglas: `{RULES_PATH.relative_to(ROOT)}`",
        f"Distancia máxima: **{settings.max_distance_miles} mi** (R03).",
        "",
    ]
    for s in summaries:
        status = "OK" if s["reconciled"] else "FAIL"
        lines += [
            f"## {s['mes']} — reconciliación {status}",
            "",
            f"| métrica | valor |",
            f"|---|---:|",
            f"| leídas | {s['rows_read']} |",
            f"| aceptadas | {s['rows_accepted']} |",
            f"| cuarentena | {s['rows_quarantine']} |",
            f"| leídas = aceptadas + cuarentena | `{s['reconciled']}` |",
            "",
            "| regla | severidad | cantidad |",
            "|---|---|---:|",
        ]
        for r in rules:
            lines.append(
                f"| {r.id} ({r.name}) | {r.severity} | {s['per_rule'].get(r.id, 0)} |"
            )
        lines.append("")

    lines += [
        "## Severidades",
        "",
        "- **reject** → fila a cuarentena (`violated_rules`).",
        "- **warn** → fila aceptada con `quality_flags`.",
        "",
        "## R09 (regla propia)",
        "",
        "Duración > 8 h (480 min): exploración mostró P99.9 ≈ 110 min; "
        "valores mayores se tratan como error de reloj/GPS.",
        "",
    ]
    md = base.with_suffix(".md")
    md.write_text("\n".join(lines), encoding="utf-8")
    return md


def run_quality(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)
    rules = load_rules()

    print(f"[quality] ENV={settings.env} MES={target.label} compare={compare.label}")
    print(f"[quality] reglas={len(rules)} max_distance={settings.max_distance_miles} mi")

    con = connect(settings)
    summaries: list[dict[str, Any]] = []
    failed = False

    for ref in (target, compare):
        print(f"[quality] procesando {ref.label}…")
        try:
            summary = process_month(
                con=con, settings=settings, ref=ref, rules=rules
            )
        except FileNotFoundError as exc:
            print(f"[error] {exc}")
            return 1
        summaries.append(summary)
        print(
            f"  leídas={summary['rows_read']} "
            f"aceptadas={summary['rows_accepted']} "
            f"cuarentena={summary['rows_quarantine']} "
            f"reconciled={summary['reconciled']}"
        )
        for rid, cnt in summary["per_rule"].items():
            if cnt:
                print(f"    {rid}: {cnt}")
        if not summary["reconciled"]:
            failed = True
            print("  ✗ reconciliación fallida")

    report = write_quality_reports(settings, target.label, rules, summaries)
    print(f"[quality] reporte: {report}")

    if failed:
        print("[quality] FAILED — reconciliación de conteos")
        return 1

    print("[quality] OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calidad y cuarentena Yellow Taxi")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_quality(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
