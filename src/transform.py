"""Parte 4 — Transformación: capa curada Parquet Hive + columnas derivadas.

Lee `data/accepted/yellow/year=/month=/`, enriquece con zonas, agrega
derivados y escribe `data/curated/yellow/year=/month=/part.parquet`.

Reprocesar un mes reemplaza solo esa partición (las demás quedan intactas).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.calidad import accepted_path
from src.config import Settings, get_settings
from src.duck import connect
from src.ingesta_airbyte import MonthRef, comparison_month, local_zones_path, parse_mes


def curated_path(settings: Settings, ref: MonthRef) -> Path:
    return (
        settings.data_dir
        / "curated"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / "part.parquet"
    )


def curated_glob(settings: Settings) -> str:
    return str(settings.data_dir / "curated" / "yellow" / "**" / "part.parquet")


def partition_counts(settings: Settings) -> dict[str, int]:
    """Conteos por partición year-month en curated (vacío si no hay datos)."""
    pattern = curated_glob(settings)
    root = settings.data_dir / "curated" / "yellow"
    if not root.exists() or not any(root.rglob("part.parquet")):
        return {}
    con = connect(settings)
    rows = con.execute(
        f"""
        SELECT source_year, source_month, count(*)::BIGINT AS n
        FROM read_parquet('{pattern.replace("'", "''")}', hive_partitioning=true)
        GROUP BY 1, 2
        ORDER BY 1, 2
        """
    ).fetchall()
    return {f"{y:04d}-{m:02d}": int(n) for y, m, n in rows}


def transform_month(*, con, settings: Settings, ref: MonthRef) -> int:
    src = accepted_path(settings, ref)
    if not src.exists():
        raise FileNotFoundError(
            f"Falta accepted {src}. Corré `make quality` antes."
        )
    zones = local_zones_path(settings)
    if not zones.exists():
        raise FileNotFoundError(f"Falta zonas {zones}.")

    out = curated_path(settings, ref)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # replace solo esta partición

    src_sql = str(src).replace("'", "''")
    zones_sql = str(zones).replace("'", "''")
    out_sql = str(out).replace("'", "''")

    # Derivados + enrich. tip_pct NULL si fare_amount <= 0.
    # avg_speed_mph NULL si duración <= 0.
    con.execute(
        f"""
        COPY (
          SELECT
            t.*,
            date_diff(
              'second', t.tpep_pickup_datetime, t.tpep_dropoff_datetime
            ) / 60.0 AS duration_min,
            CASE
              WHEN date_diff('second', t.tpep_pickup_datetime, t.tpep_dropoff_datetime) > 0
              THEN t.trip_distance / (
                date_diff('second', t.tpep_pickup_datetime, t.tpep_dropoff_datetime) / 3600.0
              )
              ELSE NULL
            END AS avg_speed_mph,
            CAST(t.tpep_pickup_datetime AS DATE) AS pickup_date,
            hour(t.tpep_pickup_datetime) AS pickup_hour,
            dayofweek(t.tpep_pickup_datetime) AS pickup_dow,
            CASE
              WHEN t.fare_amount > 0 THEN t.tip_amount / t.fare_amount
              ELSE NULL
            END AS tip_pct,
            zpu.Borough AS pu_borough,
            zpu.Zone AS pu_zone,
            zdo.Borough AS do_borough,
            zdo.Zone AS do_zone
          FROM read_parquet('{src_sql}') t
          LEFT JOIN read_csv_auto('{zones_sql}') zpu
            ON t.pu_location_id = zpu.LocationID
          LEFT JOIN read_csv_auto('{zones_sql}') zdo
            ON t.do_location_id = zdo.LocationID
        ) TO '{out_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )

    n = con.execute(
        f"SELECT num_rows FROM parquet_file_metadata('{out_sql}')"
    ).fetchone()[0]
    return int(n)


def write_partition_demo(
    settings: Settings,
    mes: str,
    before: dict[str, int],
    after: dict[str, int],
) -> Path:
    reports = settings.data_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    path = reports / f"partition_replace_{mes}.md"
    lines = [
        f"# Reproceso de partición — MES={mes}",
        "",
        "Reemplazar un mes solo toca `data/curated/yellow/year=…/month=…/`.",
        "Las demás particiones conservan el mismo conteo.",
        "",
        "| partición | antes | después | Δ |",
        "|---|---:|---:|---:|",
    ]
    keys = sorted(set(before) | set(after))
    for k in keys:
        b, a = before.get(k, 0), after.get(k, 0)
        lines.append(f"| {k} | {b} | {a} | {a - b} |")
    lines += [
        "",
        f"Demo generada al correr `make transform-host MES={mes}`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

    # JSON para asserts
    path.with_suffix(".json").write_text(
        json.dumps({"before": before, "after": after}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def run_transform(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)

    print(f"[transform] ENV={settings.env} MES={target.label} compare={compare.label}")

    before = partition_counts(settings)
    if before:
        print(f"[transform] particiones antes: {before}")

    con = connect(settings)
    for ref in (target, compare):
        print(f"[transform] curated {ref.label}…")
        try:
            n = transform_month(con=con, settings=settings, ref=ref)
        except FileNotFoundError as exc:
            print(f"[error] {exc}")
            return 1
        print(f"  ✓ {n} filas → {curated_path(settings, ref).relative_to(settings.data_dir)}")

    after = partition_counts(settings)
    print(f"[transform] particiones después: {after}")
    demo = write_partition_demo(settings, target.label, before, after)
    print(f"[transform] demo partición: {demo}")

    # Otras particiones (si las hubiera) no deben cambiar al reprocesar target+compare
    for k, b in before.items():
        if k in {target.label, compare.label}:
            continue
        if after.get(k) != b:
            print(f"[error] partición ajena {k} cambió: {b} → {after.get(k)}")
            return 1

    print("[transform] OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transformación capa curada Hive")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_transform(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
