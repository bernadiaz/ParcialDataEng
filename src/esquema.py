"""Parte 2 — Contrato de esquema, normalización snake_case y unificación.

- Compara el Parquet real vs `contracts/yellow_schema.yaml`
- Reporta: faltantes, nuevas, tipos distintos
- Normaliza aliases → snake_case + CAST al tipo destino
- `cbd_congestion_fee` ausente (2024) → NULL
- Columna nueva no contratada → ignore + warning
- Columna requerida faltante → falla el pipeline
- Escribe staging Hive: `data/staging/yellow/year=/month=/`
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.config import ROOT, Settings, get_settings
from src.duck import connect
from src.ingesta_airbyte import MonthRef, comparison_month, local_yellow_path, parse_mes

CONTRACT_PATH = ROOT / "contracts" / "yellow_schema.yaml"

# Familias de tipos DuckDB consideradas compatibles (solo warning de cast).
_TYPE_FAMILIES: dict[str, str] = {
    "TINYINT": "int",
    "SMALLINT": "int",
    "INTEGER": "int",
    "BIGINT": "int",
    "HUGEINT": "int",
    "UTINYINT": "int",
    "USMALLINT": "int",
    "UINTEGER": "int",
    "UBIGINT": "int",
    "FLOAT": "float",
    "DOUBLE": "float",
    "DECIMAL": "float",
    "VARCHAR": "str",
    "TEXT": "str",
    "STRING": "str",
    "TIMESTAMP": "ts",
    "TIMESTAMP_NS": "ts",
    "TIMESTAMP WITH TIME ZONE": "ts",
    "DATE": "date",
    "BOOLEAN": "bool",
}


@dataclass
class ColumnContract:
    name: str
    type: str
    required: bool
    nullable: bool
    source_aliases: list[str]
    notes: str | None = None


@dataclass
class SchemaDiff:
    source_file: str
    year: int
    month: int
    source_columns: dict[str, str]
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    type_mismatches: list[dict[str, str]] = field(default_factory=list)
    mapped: dict[str, str] = field(default_factory=dict)  # dest -> source col
    warnings: list[str] = field(default_factory=list)
    fatal: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.fatal


def load_contract(path: Path = CONTRACT_PATH) -> list[ColumnContract]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cols: list[ColumnContract] = []
    for c in raw["columns"]:
        cols.append(
            ColumnContract(
                name=c["name"],
                type=str(c["type"]).upper(),
                required=bool(c.get("required", True)),
                nullable=bool(c.get("nullable", True)),
                source_aliases=[str(a) for a in c.get("source_aliases", [c["name"]])],
                notes=c.get("notes"),
            )
        )
    return cols


def _norm_type(t: str) -> str:
    t = t.upper().strip()
    # DECIMAL(10,2) → DECIMAL
    if t.startswith("DECIMAL"):
        return "DECIMAL"
    if t.startswith("TIMESTAMP"):
        return "TIMESTAMP"
    return t


def _family(t: str) -> str:
    return _TYPE_FAMILIES.get(_norm_type(t), _norm_type(t))


def read_parquet_schema(con, path: Path) -> dict[str, str]:
    rows = con.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)",
        [str(path)],
    ).fetchall()
    return {r[0]: str(r[1]) for r in rows}


def resolve_alias(source_cols: dict[str, str], aliases: list[str]) -> str | None:
    lower_map = {k.lower(): k for k in source_cols}
    for alias in aliases:
        if alias in source_cols:
            return alias
        if alias.lower() in lower_map:
            return lower_map[alias.lower()]
    return None


def compare_schema(
    *,
    source_file: str,
    year: int,
    month: int,
    source_cols: dict[str, str],
    contract: list[ColumnContract],
    cbd_strategy: str,
) -> SchemaDiff:
    diff = SchemaDiff(
        source_file=source_file,
        year=year,
        month=month,
        source_columns=dict(source_cols),
    )
    claimed: set[str] = set()

    for col in contract:
        src = resolve_alias(source_cols, col.source_aliases)
        if src is None:
            if col.name == "cbd_congestion_fee" and cbd_strategy == "null":
                diff.missing_optional.append(col.name)
                diff.warnings.append(
                    f"{col.name}: ausente → se materializa NULL (estrategia={cbd_strategy})"
                )
                continue
            if col.required:
                diff.missing_required.append(col.name)
                diff.fatal.append(f"columna requerida faltante: {col.name}")
            else:
                diff.missing_optional.append(col.name)
                diff.warnings.append(f"columna opcional faltante: {col.name}")
            continue

        claimed.add(src)
        diff.mapped[col.name] = src
        src_type = _norm_type(source_cols[src])
        dst_type = _norm_type(col.type)
        if src_type != dst_type:
            entry = {
                "column": col.name,
                "source": src,
                "source_type": source_cols[src],
                "contract_type": col.type,
                "compatible": str(_family(src_type) == _family(dst_type)).lower(),
            }
            diff.type_mismatches.append(entry)
            if _family(src_type) == _family(dst_type):
                diff.warnings.append(
                    f"tipo distinto (cast seguro): {src} {source_cols[src]} → {col.name} {col.type}"
                )
            else:
                diff.warnings.append(
                    f"tipo distinto (cast forzado): {src} {source_cols[src]} → {col.name} {col.type}"
                )

    for name in source_cols:
        if name not in claimed:
            diff.unexpected.append(name)
            diff.warnings.append(
                f"columna nueva no contratada (ignore): {name} ({source_cols[name]})"
            )

    return diff


def build_select_sql(
    *,
    parquet_path: Path,
    contract: list[ColumnContract],
    diff: SchemaDiff,
    source_file: str,
    year: int,
    month: int,
    cbd_strategy: str,
) -> str:
    """SELECT tipado + linaje. Columnas no contratadas no se proyectan."""
    projections: list[str] = []
    for col in contract:
        src = diff.mapped.get(col.name)
        if src is None:
            if col.name == "cbd_congestion_fee" and cbd_strategy == "null":
                projections.append(f"CAST(NULL AS {col.type}) AS {col.name}")
            else:
                projections.append(f"CAST(NULL AS {col.type}) AS {col.name}")
            continue
        # Quote source identifier if needed
        src_ref = f'"{src}"' if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", src) else src
        projections.append(f"CAST({src_ref} AS {col.type}) AS {col.name}")

    projections.append(f"CAST('{source_file}' AS VARCHAR) AS source_file")
    projections.append(f"CAST({year} AS INTEGER) AS source_year")
    projections.append(f"CAST({month} AS INTEGER) AS source_month")

    cols_sql = ",\n    ".join(projections)
    # path escapado para SQL
    path_sql = str(parquet_path).replace("'", "''")
    return f"SELECT\n    {cols_sql}\nFROM read_parquet('{path_sql}')"


def staging_path(settings: Settings, ref: MonthRef) -> Path:
    return (
        settings.data_dir
        / "staging"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / "part.parquet"
    )


def write_schema_report(
    settings: Settings,
    mes: str,
    diffs: list[SchemaDiff],
) -> Path:
    reports = settings.data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    base = reports / f"schema_report_{mes}"

    # JSON detalle
    payload: list[dict[str, Any]] = []
    for d in diffs:
        payload.append(
            {
                "source_file": d.source_file,
                "year": d.year,
                "month": d.month,
                "ok": d.ok,
                "missing_required": d.missing_required,
                "missing_optional": d.missing_optional,
                "unexpected": d.unexpected,
                "type_mismatches": d.type_mismatches,
                "mapped": d.mapped,
                "warnings": d.warnings,
                "fatal": d.fatal,
            }
        )
    base.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # CSV resumen
    csv_path = base.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "source_file",
                "year",
                "month",
                "ok",
                "missing_required",
                "missing_optional",
                "unexpected",
                "type_mismatches",
                "warnings_count",
            ],
        )
        w.writeheader()
        for d in diffs:
            w.writerow(
                {
                    "source_file": d.source_file,
                    "year": d.year,
                    "month": d.month,
                    "ok": d.ok,
                    "missing_required": "|".join(d.missing_required),
                    "missing_optional": "|".join(d.missing_optional),
                    "unexpected": "|".join(d.unexpected),
                    "type_mismatches": "|".join(
                        f"{m['source']}:{m['source_type']}->{m['contract_type']}"
                        for m in d.type_mismatches
                    ),
                    "warnings_count": len(d.warnings),
                }
            )

    # Markdown legible
    lines = [
        f"# Schema report — MES={mes}",
        "",
        f"Contrato: `{CONTRACT_PATH.relative_to(ROOT)}`",
        "",
    ]
    for d in diffs:
        status = "OK" if d.ok else "FAIL"
        lines += [
            f"## {d.source_file} ({d.year:04d}-{d.month:02d}) — {status}",
            "",
            f"- Faltantes requeridas: `{d.missing_required or '—'}`",
            f"- Faltantes opcionales: `{d.missing_optional or '—'}`",
            f"- Nuevas (ignore): `{d.unexpected or '—'}`",
            f"- Tipos distintos: `{len(d.type_mismatches)}`",
            "",
        ]
        if d.type_mismatches:
            lines.append("| columna | source | source_type | contract_type | compatible |")
            lines.append("|---|---|---|---|---|")
            for m in d.type_mismatches:
                lines.append(
                    f"| {m['column']} | {m['source']} | {m['source_type']} | "
                    f"{m['contract_type']} | {m['compatible']} |"
                )
            lines.append("")
        if d.warnings:
            lines.append("Warnings:")
            for wmsg in d.warnings:
                lines.append(f"- {wmsg}")
            lines.append("")
        if d.fatal:
            lines.append("Fatal:")
            for fmsg in d.fatal:
                lines.append(f"- {fmsg}")
            lines.append("")

    lines += [
        "## Políticas",
        "",
        "- `cbd_congestion_fee` ausente (p.ej. 2024) → **NULL** (no 0).",
        "- Columna nueva no contratada → **ignore + warning**.",
        "- Columna requerida faltante → **falla el pipeline**.",
        "",
    ]
    md_path = base.with_suffix(".md")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def normalize_month(
    *,
    con,
    settings: Settings,
    ref: MonthRef,
    contract: list[ColumnContract],
) -> SchemaDiff:
    raw_path = local_yellow_path(settings, ref)
    if not raw_path.exists():
        raise FileNotFoundError(
            f"No existe raw para {ref.label}: {raw_path}. Corré `make ingest` antes."
        )

    source_cols = read_parquet_schema(con, raw_path)
    diff = compare_schema(
        source_file=raw_path.name,
        year=ref.year,
        month=ref.month,
        source_cols=source_cols,
        contract=contract,
        cbd_strategy=settings.cbd_fee_missing_strategy,
    )
    if not diff.ok:
        return diff

    out = staging_path(settings, ref)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Reemplazo de partición del mes (idempotente)
    if out.exists():
        out.unlink()

    select_sql = build_select_sql(
        parquet_path=raw_path,
        contract=contract,
        diff=diff,
        source_file=raw_path.name,
        year=ref.year,
        month=ref.month,
        cbd_strategy=settings.cbd_fee_missing_strategy,
    )
    out_sql = str(out).replace("'", "''")
    print(f"  → staging {out.relative_to(settings.data_dir)}")
    con.execute(
        f"COPY ({select_sql}) TO '{out_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )

    # Sanity: contar filas staging vs raw metadata
    n_raw = con.execute(
        "SELECT num_rows FROM parquet_file_metadata(?)", [str(raw_path)]
    ).fetchone()[0]
    n_stg = con.execute(
        "SELECT num_rows FROM parquet_file_metadata(?)", [str(out)]
    ).fetchone()[0]
    if n_raw != n_stg:
        diff.fatal.append(f"conteo staging≠raw: staging={n_stg} raw={n_raw}")
    else:
        print(f"  ✓ {ref.label}: {n_stg} filas normalizadas")

    return diff


def run_schema(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)
    contract = load_contract()

    print(f"[schema] ENV={settings.env} MES={target.label} compare={compare.label}")
    print(f"[schema] contrato={CONTRACT_PATH} ({len(contract)} columnas)")

    con = connect(settings)
    diffs: list[SchemaDiff] = []
    fatal = False

    for ref in (target, compare):
        print(f"[schema] normalizando {ref.label}…")
        try:
            diff = normalize_month(
                con=con, settings=settings, ref=ref, contract=contract
            )
        except FileNotFoundError as exc:
            print(f"[error] {exc}")
            return 1
        diffs.append(diff)
        for w in diff.warnings:
            print(f"  ! {w}")
        for fmsg in diff.fatal:
            print(f"  ✗ {fmsg}")
            fatal = True

    report = write_schema_report(settings, target.label, diffs)
    print(f"[schema] reporte: {report}")

    if fatal:
        print("[schema] FAILED — hay columnas requeridas faltantes u otros fatales")
        return 1

    # Resumen unificado: ambos meses leíbles como una tabla
    pattern = str(settings.data_dir / "staging" / "yellow" / "**" / "part.parquet")
    n_all = con.execute(
        "SELECT count(*) FROM read_parquet(?, hive_partitioning=true)",
        [pattern],
    ).fetchone()[0]
    print(f"[schema] OK — staging unificado ({n_all} filas en particiones year/month)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validación y normalización de esquema")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_schema(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
