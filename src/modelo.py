"""Modelo estrella mínimo en DuckDB (dev) — fact / dims / agg.

Granularidad (documentar en README):
- dim_zone: 1 fila por LocationID (taxi_zone_lookup)
- dim_date: 1 fila por fecha de pickup presente en fact_trips
- fact_trips: 1 fila por viaje aceptado/curado
- agg_zone_hour: 1 fila por (pu_location_id, pickup_date, pickup_hour)

En `ENV=prod` esto se materializa vía dbt en Snowflake; acá dejamos el
warehouse local `data/warehouse/nyc_taxi.duckdb` (útil para DataGrip).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from src.config import Settings, get_settings
from src.duck import connect
from src.ingesta_airbyte import MonthRef, comparison_month, local_zones_path, parse_mes
from src.transform import curated_glob, curated_path


def warehouse_path(settings: Settings) -> Path:
    return settings.data_dir / "warehouse" / "nyc_taxi.duckdb"


def build_model(*, settings: Settings, refs: list[MonthRef]) -> tuple[Path, dict[str, int]]:
    for ref in refs:
        p = curated_path(settings, ref)
        if not p.exists():
            raise FileNotFoundError(
                f"Falta curated {p}. Corré `make transform` antes."
            )

    wh = warehouse_path(settings)
    wh.parent.mkdir(parents=True, exist_ok=True)
    if wh.exists():
        wh.unlink()
        wal = Path(str(wh) + ".wal")
        if wal.exists():
            wal.unlink()

    # Conexión persistente al archivo warehouse
    con = duckdb.connect(str(wh))
    con.execute(f"SET threads TO {settings.duckdb_threads}")
    con.execute(f"SET memory_limit TO '{settings.duckdb_memory_limit}'")

    pattern = curated_glob(settings).replace("'", "''")
    zones = str(local_zones_path(settings)).replace("'", "''")

    # Filtrar a los meses del run (no mezclar histórico ajeno si aparece)
    month_filters = " OR ".join(
        f"(source_year = {r.year} AND source_month = {r.month})" for r in refs
    )

    con.execute("CREATE SCHEMA IF NOT EXISTS marts")
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")

    con.execute(
        f"""
        CREATE OR REPLACE TABLE staging.curated_trips AS
        SELECT *
        FROM read_parquet('{pattern}', hive_partitioning=true)
        WHERE {month_filters}
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE TABLE marts.dim_zone AS
        SELECT
          LocationID::BIGINT AS zone_id,
          Borough AS borough,
          Zone AS zone_name,
          service_zone
        FROM read_csv_auto('{zones}')
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE marts.dim_date AS
        SELECT DISTINCT
          pickup_date AS date_id,
          year(pickup_date) AS year,
          month(pickup_date) AS month,
          day(pickup_date) AS day,
          dayofweek(pickup_date) AS dow,
          strftime(pickup_date, '%A') AS dow_name
        FROM staging.curated_trips
        WHERE pickup_date IS NOT NULL
        ORDER BY 1
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE marts.fact_trips AS
        SELECT
          row_number() OVER () AS trip_sk,
          vendor_id,
          tpep_pickup_datetime,
          tpep_dropoff_datetime,
          passenger_count,
          trip_distance,
          ratecode_id,
          store_and_fwd_flag,
          pu_location_id AS pu_zone_id,
          do_location_id AS do_zone_id,
          payment_type,
          fare_amount,
          extra,
          mta_tax,
          tip_amount,
          tolls_amount,
          improvement_surcharge,
          total_amount,
          congestion_surcharge,
          airport_fee,
          cbd_congestion_fee,
          duration_min,
          avg_speed_mph,
          pickup_date AS date_id,
          pickup_hour,
          pickup_dow,
          tip_pct,
          pu_borough,
          pu_zone,
          do_borough,
          do_zone,
          source_file,
          source_year,
          source_month,
          quality_flags
        FROM staging.curated_trips
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE marts.agg_zone_hour AS
        SELECT
          pu_zone_id,
          date_id,
          pickup_hour,
          count(*)::BIGINT AS trips,
          sum(total_amount) AS total_revenue,
          avg(duration_min) AS avg_duration_min
        FROM marts.fact_trips
        GROUP BY 1, 2, 3
        """
    )

    # Conteos de control
    stats = {
        "dim_zone": con.execute("SELECT count(*) FROM marts.dim_zone").fetchone()[0],
        "dim_date": con.execute("SELECT count(*) FROM marts.dim_date").fetchone()[0],
        "fact_trips": con.execute("SELECT count(*) FROM marts.fact_trips").fetchone()[0],
        "agg_zone_hour": con.execute(
            "SELECT count(*) FROM marts.agg_zone_hour"
        ).fetchone()[0],
    }
    con.close()
    return wh, stats


def run_modelo(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)
    refs = [target, compare]

    print(f"[model] ENV={settings.env} MES={target.label} compare={compare.label}")
    try:
        wh, stats = build_model(settings=settings, refs=refs)
    except FileNotFoundError as exc:
        print(f"[error] {exc}")
        return 1

    print(f"[model] warehouse: {wh}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("[model] OK — DataGrip: DuckDB → este archivo")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modelo estrella DuckDB")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_modelo(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
