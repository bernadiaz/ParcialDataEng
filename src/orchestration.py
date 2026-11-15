"""Dagster orchestration of the pipeline. `make all` runs it; `make dagster-ui` opens the UI.

Asset graph (monthly partitions, key = YYYY-MM):

    taxi_zone_lookup ─┐
    raw_yellow_trips ─┴─> yellow_schema_report ─> curated_yellow_trips ─> raw/yellow_trips ─┐
                                                   (asset check: reconciliation)            ├─> dbt models
    curated zones ─────────────────────────────────────────────────────> raw/taxi_zones ───┘   (staging ->
                                                                                                marts) ─> resultados_md

raw/yellow_trips and raw/taxi_zones are the warehouse tables loaded by src/load_snowflake.py.
They share their asset keys with the dbt sources, so the lineage continues into the dbt models.
Each step keeps its own module (src/*.py). Dagster adds partitions, run history, lineage and
asset checks, and the steps still run one by one from the Makefile.

    python -m src.orchestration --mes 2025-01      # the month and the same month of the previous year
    dagster dev -m src.orchestration -p 3001       # UI

No `from __future__ import annotations` here: Dagster inspects the real type of `context`.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from src.config import ROOT, Month, Settings, months_for, track_step

os.environ.setdefault("DAGSTER_HOME", str(Settings.from_env().data_dir / "dagster_home"))
os.environ.setdefault("DUCKDB_WAREHOUSE_PATH", str(Settings.from_env().warehouse_db))  # dbt duckdb target
Path(os.environ["DAGSTER_HOME"]).mkdir(parents=True, exist_ok=True)
(Path(os.environ["DAGSTER_HOME"]) / "dagster.yaml").touch(exist_ok=True)  # default local instance, no warning

from dagster import (  # noqa: E402
    AssetCheckResult,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    Config,
    DagsterInstance,
    Definitions,
    DynamicPartitionsDefinition,
    MaterializeResult,
    MetadataValue,
    asset,
    define_asset_job,
    materialize,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets, get_asset_key_for_model  # noqa: E402

from src import calidad, esquema, load_snowflake, resultados  # noqa: E402
from src.ingesta_airbyte import Ingestor, IngestionLog  # noqa: E402

DBT_DIR = ROOT / "dbt_taxi"
# Dynamic partitions = only the months the pipeline actually processes (scope of the exam: the
# assigned month and the same month of the previous year). `make all MES=...` registers them, so
# the UI shows 2/2 materialized instead of 2 out of every month since 2024.
MONTHLY = DynamicPartitionsDefinition(name="months")


def _target() -> str:
    if os.environ.get("DBT_TARGET"):
        return os.environ["DBT_TARGET"]
    if os.environ.get("WAREHOUSE", "snowflake").lower() == "duckdb":
        return "duckdb"
    return "snowflake_keypair" if os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH", "").strip() else "snowflake_browser"


DBT_EXE = str(Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt"))  # dbt of this .venv
DBT_PROJECT = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR, target=_target())


def _manifest_is_stale() -> bool:
    manifest = Path(DBT_PROJECT.manifest_path)
    if not manifest.exists():
        return True
    sources = [p for d in ("models", "macros", "tests") for p in (DBT_DIR / d).rglob("*") if p.is_file()]
    sources.append(DBT_DIR / "dbt_project.yml")
    return max(p.stat().st_mtime for p in sources) > manifest.stat().st_mtime


if _manifest_is_stale():  # the dbt manifest drives the dbt assets: refresh it when the project changed
    subprocess.run(
        [DBT_EXE, "parse", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR), "--target", _target(), "--quiet"],
        check=True,
    )


def _settings() -> Settings:
    return Settings.from_env()


# --- ingestion -------------------------------------------------------------------------------------
@asset(group_name="ingestion", kinds={"airbyte", "s3"}, description="TLC taxi zone lookup landed in S3 and mirrored (once, skipped while the hash matches).")
def taxi_zone_lookup(context: AssetExecutionContext) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, "ingest-zones", "static"):
        Ingestor(settings).zones()
    entries = IngestionLog(settings).last_ok("zones", "static")
    return MaterializeResult(metadata={
        "files": MetadataValue.json([e["file"] for e in entries]),
        "sha256": entries[0]["sha256"] if entries else "",
        "rows": sum(e["row_count"] or 0 for e in entries),
    })


@asset(partitions_def=MONTHLY, group_name="ingestion", kinds={"airbyte", "s3"},
       description="Monthly TLC yellow file landed in s3://.../raw/yellow/year=/month=/, verified (SHA-256) and logged.")
def raw_yellow_trips(context: AssetExecutionContext) -> MaterializeResult:
    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, "ingest", month.label):
        Ingestor(settings).yellow(month)
    entries = IngestionLog(settings).last_ok("yellow", month.label)
    return MaterializeResult(metadata={
        "files": MetadataValue.json([e["file"] for e in entries]),
        "bytes": sum(e["bytes"] or 0 for e in entries),
        "rows": sum(e["row_count"] or 0 for e in entries),
        "sha256": MetadataValue.json([e["sha256"] for e in entries]),
        "action": entries[-1]["action"] if entries else "",
    })


# --- schema and quality --------------------------------------------------------------------------------
@asset(partitions_def=MONTHLY, group_name="quality", kinds={"duckdb"}, deps=[raw_yellow_trips, taxi_zone_lookup],
       description="Schema contract check (contracts/yellow_schema.yaml): missing, new and retyped columns.")
def yellow_schema_report(context: AssetExecutionContext) -> MaterializeResult:
    import duckdb

    from src.config import configure_duckdb

    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, "schema", month.label):
        con = configure_duckdb(duckdb.connect(), settings)
        esquema.register_zones(con, settings, esquema.load_contract(esquema.ZONES_CONTRACT))
        report = esquema.register_yellow_month(con, settings, month, esquema.load_contract(esquema.YELLOW_CONTRACT))
    return MaterializeResult(metadata={
        "status": report.status,
        "missing_optional (NULL)": MetadataValue.json(report.missing_optional),
        "new_columns (ignored)": MetadataValue.json(report.new_columns),
        "type_mismatches": MetadataValue.json(report.type_mismatches),
        "cast_failures": MetadataValue.json(report.cast_failures),
    })


@asset(partitions_def=MONTHLY, group_name="quality", kinds={"duckdb", "parquet"}, deps=[yellow_schema_report],
       check_specs=[AssetCheckSpec("reconciliation", asset="curated_yellow_trips",
                                   description="rows read = rows accepted + rows quarantined")],
       description="Quality gate: accepted rows (curated Parquet, year/month partition) and quarantine with the violated rules.")
def curated_yellow_trips(context: AssetExecutionContext) -> MaterializeResult:
    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, "quality", month.label):
        result = calidad.run_month(settings, month)  # raises ReconciliationError before publishing
    return MaterializeResult(
        metadata={
            "rows_read": result.rows_read,
            "rows_accepted": result.rows_accepted,
            "rows_quarantined": result.rows_quarantined,
            "rows_with_warnings": result.rows_with_warnings,
            "violations": MetadataValue.json(result.violations),
            "quality_report": MetadataValue.path(str(settings.reports_dir / "quality" / f"quality_report_{month.label}.md")),
        },
        check_results=[AssetCheckResult(
            check_name="reconciliation",
            passed=result.rows_read == result.rows_accepted + result.rows_quarantined,
            metadata={"read": result.rows_read, "accepted": result.rows_accepted, "quarantined": result.rows_quarantined},
        )],
    )


# --- warehouse load (asset keys = dbt sources) ----------------------------------------------------------------
@asset(key=AssetKey(["raw", "yellow_trips"]), partitions_def=MONTHLY, group_name="warehouse", kinds={"snowflake"},
       deps=[curated_yellow_trips],
       description="RAW.YELLOW_TRIPS: the month is deleted and reloaded in one transaction (idempotent).")
def warehouse_raw_yellow_trips(context: AssetExecutionContext) -> MaterializeResult:
    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, f"load-{settings.warehouse}", month.label):
        result = load_snowflake.load_months(settings, [month], include_zones=False)[0]
    return MaterializeResult(metadata={"rows_loaded": result.rows_loaded, "rows_replaced": result.rows_deleted,
                                       "warehouse": settings.warehouse})


@asset(key=AssetKey(["raw", "taxi_zones"]), group_name="warehouse", kinds={"snowflake"}, deps=[taxi_zone_lookup],
       description="RAW.TAXI_ZONES: full reload of the 265 zones.")
def warehouse_raw_taxi_zones(context: AssetExecutionContext) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, f"load-zones-{settings.warehouse}", "static"):
        result = load_snowflake.load_months(settings, [], include_zones=True)[0]
    return MaterializeResult(metadata={"rows_loaded": result.rows_loaded})


# --- dbt (staging -> intermediate -> marts) --------------------------------------------------------------------
@dbt_assets(manifest=DBT_PROJECT.manifest_path, project=DBT_PROJECT)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """dbt build. fact_trips / agg_zone_hour only reprocess the months in DBT_MONTHS (set by make)."""
    settings = _settings()
    with track_step(settings, "dbt", os.environ.get("DBT_MONTHS", "all") or "all"):
        yield from dbt.cli(["build"], context=context).stream()


# --- business questions ------------------------------------------------------------------------------------------
class QuestionsConfig(Config):
    mes: str = os.environ.get("MES", "2025-01")


@asset(group_name="analytics", kinds={"sql"},
       deps=[get_asset_key_for_model([dbt_models], name) for name in ("fact_trips", "agg_zone_hour", "dim_zone")],
       description="sql/q1..q6 against the marts -> RESULTADOS.md")
def resultados_md(context: AssetExecutionContext, config: QuestionsConfig) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, "questions", config.mes):
        path = resultados.write_results(settings, Month.parse(config.mes))
    return MaterializeResult(metadata={"path": MetadataValue.path(str(path))})


MONTHLY_ASSETS = [raw_yellow_trips, yellow_schema_report, curated_yellow_trips, warehouse_raw_yellow_trips]
ALL_ASSETS = [taxi_zone_lookup, *MONTHLY_ASSETS, warehouse_raw_taxi_zones, dbt_models, resultados_md]
RESOURCES = {"dbt": DbtCliResource(project_dir=DBT_PROJECT, profiles_dir=str(DBT_DIR), target=_target(),
                                   dbt_executable=DBT_EXE)}

defs = Definitions(
    assets=ALL_ASSETS,
    resources=RESOURCES,
    jobs=[
        define_asset_job("monthly_pipeline", AssetSelection.assets(*MONTHLY_ASSETS), partitions_def=MONTHLY,
                         description="ingest -> schema -> quality -> load for one month"),
        define_asset_job("reference_data", AssetSelection.assets(taxi_zone_lookup, warehouse_raw_taxi_zones)),
        define_asset_job("warehouse_models", AssetSelection.assets(dbt_models, resultados_md),
                         description="dbt build + RESULTADOS.md"),
    ],
)


def register_months(instance: DagsterInstance, labels: list[str]) -> None:
    """Adds the processed months as partitions of the monthly assets (idempotent)."""
    new = [label for label in labels if not instance.has_dynamic_partition(MONTHLY.name, label)]
    if new:
        instance.add_dynamic_partitions(MONTHLY.name, new)


def run(mes: str) -> int:
    """make all: zones, each month (partition), zones load, dbt and questions. One Dagster run each."""
    instance = DagsterInstance.get()
    months = months_for(mes)
    register_months(instance, [m.label for m in months])
    os.environ["DBT_MONTHS"] = ",".join(m.label for m in months)
    os.environ["MES"] = mes

    def step(selection: list, partition_key: str | None = None, run_config: dict | None = None) -> bool:
        result = materialize(ALL_ASSETS, selection=AssetSelection.assets(*selection), partition_key=partition_key, instance=instance,
                             resources=RESOURCES, run_config=run_config, raise_on_error=False,
                             tags={"mes": mes})
        return result.success

    plan = [(lambda: step([taxi_zone_lookup]))]
    plan += [(lambda m=m: step(MONTHLY_ASSETS, partition_key=m.label)) for m in months]
    plan += [
        lambda: step([warehouse_raw_taxi_zones]),
        lambda: step([dbt_models, resultados_md], run_config={"ops": {"resultados_md": {"config": {"mes": mes}}}}),
    ]
    for action in plan:
        if not action():
            print("Dagster run failed: open `make dagster-ui` (Runs) for the step logs.", file=sys.stderr)
            return 1
    print(f"Pipeline finished for {', '.join(m.label for m in months)}. Runs are in the Dagster UI (make dagster-ui).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", required=True, help="assigned month YYYY-MM")
    return run(parser.parse_args(argv).mes)


if __name__ == "__main__":
    sys.exit(main())
