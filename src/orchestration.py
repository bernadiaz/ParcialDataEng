"""Dagster orchestration of the pipeline. `make all` runs it; the UI is http://localhost:3003.

Asset graph (monthly partitions, key = YYYY-MM):

    taxi_zone_lookup ─┐
    raw_yellow_trips ─┴─> yellow_schema_report ─> curated_yellow_trips ─> raw/yellow_trips ─┐
                                                   (asset check: reconciliation)            ├─> dbt models ─┬─> resultados_md ─────┐
    taxi_zone_lookup ──────────────────────────────────────────────────> raw/taxi_zones ───┘   (staging ->  │                      ├─> superset_respaldo
                                                                                                marts ->     └─> superset_dashboards ┘
                                                                                                evidence)

resultados_md writes results/YYYY/RESULTS_MM.md, and superset_respaldo the Superset dashboards that back it (one per month
of the year of MES, plus the 12 months of the year), compares both and writes the result in the report.

raw/yellow_trips, raw/taxi_zones, raw/quality_* and raw/schema_findings are the warehouse tables loaded by src/load_snowflake.py.
They share their asset keys with the dbt sources, so the lineage continues into the dbt models.
Each step keeps its own module (src/*.py). Dagster adds partitions, run history, lineage and
asset checks, and the steps still run one by one from the Makefile.

`make all` materializes every asset, in order, so the whole lineage ends up green. The run history
goes to the Postgres of docker compose (src/dagster_instance.py), which the Dagster UI container
reads, so http://localhost:3003 shows each run as soon as it finishes.

    python -m src.orchestration --mes 2025-01      # the month and the same month of the previous year
    python -m src.orchestration --anio 2025        # the 12 months of 2025, one run each (a month that cannot run is skipped)

MES can be any month from 2010-01 (compared with 2009-01, the first TLC Parquet file) to the last month
the TLC has published. Both are checked before anything runs. A month without data to compare gets a report
that says so (src/resultados.py), and never replaces a report that has figures.
    python -m src.run_tool dagster-ui 3003         # local UI, only when docker compose is not running

No `from __future__ import annotations` here: Dagster inspects the real type of `context`.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import FIRST_TLC_MONTH, ROOT, YELLOW_URL_TEMPLATE, Month, Settings, dbt_target, months_for, track_step

os.environ.setdefault("DAGSTER_HOME", str(Settings.from_env().data_dir / "dagster_home"))
os.environ.setdefault("DUCKDB_WAREHOUSE_PATH", str(Settings.from_env().warehouse_db))  # dbt duckdb target
Path(os.environ["DAGSTER_HOME"]).mkdir(parents=True, exist_ok=True)
(Path(os.environ["DAGSTER_HOME"]) / "dagster.yaml").touch(exist_ok=True)  # default local instance, no warning

from dagster import (  # noqa: E402
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetKey,
    AssetSelection,
    AssetSpec,
    Config,
    DagsterInstance,
    Definitions,
    DynamicPartitionsDefinition,
    MaterializeResult,
    MetadataValue,
    asset,
    define_asset_job,
    materialize,
    multi_asset,
)
from dagster_dbt import (  # noqa: E402
    DagsterDbtTranslator,
    DagsterDbtTranslatorSettings,
    DbtCliResource,
    DbtProject,
    dbt_assets,
    get_asset_key_for_model,
)

from src import (  # noqa: E402
    calidad,
    dagster_instance,
    dashboards,
    esquema,
    evidencia,
    load_snowflake,
    observability,
    respaldo,
    resultados,
)
from src.ingesta_airbyte import Ingestor, IngestionLog, month_published  # noqa: E402

DBT_DIR = ROOT / "dbt_taxi"
# Dynamic partitions = only the months the pipeline actually processes (scope of the exam: the
# assigned month and the same month of the previous year). `make all MES=...` registers them, so
# the UI shows 2/2 materialized instead of 2 out of every month since 2024.
MONTHLY = DynamicPartitionsDefinition(name="months")


def _target() -> str:
    return dbt_target()


DBT_EXE = str(Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt"))  # dbt of this .venv
# DBT_TARGET_PATH lets the Dagster UI container keep its own manifest instead of writing into the
# repository it mounts read only. On the host it is dbt's default, dbt_taxi/target.
DBT_PROJECT = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR, target=_target(),
                         target_path=Path(os.environ.get("DBT_TARGET_PATH", "").strip() or "target"))


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
        result = load_snowflake.load_months(settings, [month], include_zones=False, include_quarantine=False,
                                            include_quality=False)[0]
    return MaterializeResult(metadata={"rows_loaded": result.rows_loaded, "rows_replaced": result.rows_deleted,
                                       "warehouse": settings.warehouse})


@asset(key=AssetKey(["raw", "yellow_quarantine"]), partitions_def=MONTHLY, group_name="warehouse",
       kinds={"snowflake", "s3", "parquet"}, deps=[curated_yellow_trips],
       description="Quarantine of the month: every rejected row as read (contract columns), its source file and row "
                   "number and the reject rules it violated. Loaded into RAW.YELLOW_QUARANTINE (the month is replaced) "
                   "and, in cloud mode, copied to s3://<bucket>/quarantine/yellow/year=/month=/.")
def warehouse_raw_yellow_quarantine(context: AssetExecutionContext) -> MaterializeResult:
    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, f"quarantine-{settings.warehouse}", month.label):
        s3_uri = calidad.publish_quarantine(settings, month)
        result = load_snowflake.load_months(settings, [month], include_zones=False, include_trips=False,
                                            include_quality=False)[0]
        by_rule = calidad.quarantine_by_rule(settings, month)
    return MaterializeResult(metadata={
        "rows_loaded": result.rows_loaded,
        "rows_replaced": result.rows_deleted,
        "rows_by_rule": MetadataValue.json(by_rule),
        "warehouse_table": f"{'raw' if settings.warehouse == 'duckdb' else 'RAW'}.yellow_quarantine",
        "local_file": MetadataValue.path(str(calidad.quarantine_file(settings, month))),
        "s3": s3_uri or "offline mode: local file only",
    })


QUALITY_KEYS = [AssetKey(["raw", table]) for table in load_snowflake.QUALITY_TABLES]
QUALITY_DESCRIPTIONS = {
    "quality_summary": "Quality gate of the month, as reported by the run that loaded it: rows read, accepted, quarantined, with warnings.",
    "quality_rules": "Rows violating each quality rule in the month, rejects and warnings.",
    "schema_findings": "What the month's file brought compared with contracts/yellow_schema.yaml (one row per finding).",
}


@multi_asset(
    name="warehouse_raw_quality", partitions_def=MONTHLY,
    specs=[AssetSpec(key, deps=[curated_yellow_trips, AssetKey(["raw", "yellow_trips"])], group_name="warehouse", kinds={"snowflake"},
                     description=QUALITY_DESCRIPTIONS[key.path[-1]]) for key in QUALITY_KEYS])
def warehouse_raw_quality(context: AssetExecutionContext):
    """The quality and schema reports of the month, from the local control database to the warehouse (replaced as a whole)."""
    settings, month = _settings(), Month.parse(context.partition_key)
    with track_step(settings, f"quality-report-{settings.warehouse}", month.label):
        results = load_snowflake.load_months(settings, [month], include_zones=False, include_trips=False, include_quarantine=False)
    published = [r.mes for r in results]
    for key in QUALITY_KEYS:
        yield MaterializeResult(asset_key=key, metadata={"months_published": MetadataValue.json(published),
                                                         "warehouse": settings.warehouse})


@asset(key=AssetKey(["raw", "taxi_zones"]), group_name="warehouse", kinds={"snowflake"}, deps=[taxi_zone_lookup],
       description="RAW.TAXI_ZONES: full reload of the 265 zones.")
def warehouse_raw_taxi_zones(context: AssetExecutionContext) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, f"load-zones-{settings.warehouse}", "static"):
        result = load_snowflake.load_months(settings, [], include_zones=True)[0]
    return MaterializeResult(metadata={"rows_loaded": result.rows_loaded})


# --- dbt (staging -> intermediate -> marts) --------------------------------------------------------------------
# Every dbt test becomes a Dagster asset check, so `dbt build` never logs a test Dagster cannot place:
# - tests on the RAW sources (not_null, unique) are checks of raw/yellow_trips and raw/taxi_zones;
# - the singular tests that join two models name their model in meta.dagster.ref (dbt_taxi/tests).
DBT_TRANSLATOR = DagsterDbtTranslator(settings=DagsterDbtTranslatorSettings(enable_source_tests_as_checks=True))


@dbt_assets(manifest=DBT_PROJECT.manifest_path, project=DBT_PROJECT, dagster_dbt_translator=DBT_TRANSLATOR)
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """dbt build. fact_trips / agg_zone_hour only reprocess the months in DBT_MONTHS (set by make)."""
    settings = _settings()
    with track_step(settings, "dbt", os.environ.get("DBT_MONTHS", "all") or "all"):
        yield from dbt.cli(["build"], context=context).stream()


# --- business questions ------------------------------------------------------------------------------------------
class QuestionsConfig(Config):
    mes: str = os.environ.get("MES", "2025-01")


EVIDENCE_MODELS = [get_asset_key_for_model([dbt_models], name) for name in ("ev_comparaciones", *evidencia.TABLAS)]
MART_MODELS = [get_asset_key_for_model([dbt_models], name)
               for name in ("fact_trips", "agg_zone_hour", "dim_zone", "dim_date", "agg_quarantine_rule")]


@asset(group_name="analytics", kinds={"sql"},
       deps=[*MART_MODELS, *EVIDENCE_MODELS,
             *(get_asset_key_for_model([dbt_models], name) for name in (
                 "agg_month_profile", "agg_zone_month", "agg_hour_month", "agg_day", "agg_payment_month", "agg_airport_month",
                 "top_fare_trips"))],
       check_specs=[AssetCheckSpec("cifras_respaldadas", asset="resultados_md",
                                   description="every number of the report is shown by the Superset charts its block cites")],
       description="sql/q1..q6 and sql/contexto against the marts -> results/YYYY/RESULTS_MM.md (MES vs the same month of "
                   "the previous year, interpreted in Spanish from the numbers of the run, with the Superset chart behind "
                   "every figure) and the README")
def resultados_md(context: AssetExecutionContext, config: QuestionsConfig) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, "questions", config.mes):
        report = resultados.write_report(settings, Month.parse(config.mes))
    unbacked = [f"{c.texto} ({evidencia.seccion_corta(c.seccion)})" for c in report.sin_respaldo]
    return MaterializeResult(
        metadata={"results": MetadataValue.path(str(report.path)), "figures": len(report.cifras),
                  "figures_without_chart": len(unbacked)},
        check_results=[AssetCheckResult(
            check_name="cifras_respaldadas", passed=not unbacked and not report.avisos, severity=AssetCheckSeverity.WARN,
            metadata={"figures": len(report.cifras), "without_chart": MetadataValue.json(unbacked),
                      "differences": MetadataValue.json(report.avisos)})],
    )


@asset(group_name="analytics", kinds={"superset"},
       deps=MART_MODELS,
       description="The 7 Superset dashboards (English) on the marts, created or updated through the Superset API "
                   "(Snowflake, or the offline DuckDB copy when WAREHOUSE=duckdb).")
def superset_dashboards(context: AssetExecutionContext, config: QuestionsConfig) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, "dashboards", config.mes):
        summary = dashboards.build(settings, Month.parse(config.mes))
    return MaterializeResult(metadata={
        "superset": MetadataValue.url(dashboards.superset_url()),
        "database": summary["database"],
        "datasets": summary["datasets"],
        "dashboards": MetadataValue.json(summary["dashboards"]),
    })


@asset(group_name="analytics", kinds={"superset"},
       deps=[resultados_md, superset_dashboards, *EVIDENCE_MODELS],
       # Blocking: a report that does not match what Superset shows makes the run fail.
       check_specs=[AssetCheckSpec("superset_coincide", asset="superset_respaldo", blocking=True,
                                   description="the data Superset returns for every evidence chart is the data of the report")],
       description="Evidence dashboards (Spanish) of the reports in results/: one per month of the year of MES, with the chart "
                   "behind every figure and conclusion, and the 12 months of the year against the previous year. They are "
                   "compared with the evidence through the Superset API and the result is written in the report.")
def superset_respaldo(context: AssetExecutionContext, config: QuestionsConfig) -> MaterializeResult:
    settings = _settings()
    with track_step(settings, "evidence-dashboards", config.mes):
        # superset_dashboards has just refreshed the offline BI copy of this run.
        summary = respaldo.build(settings, Month.parse(config.mes), exportar=False)
    return MaterializeResult(
        metadata={
            "dashboards": MetadataValue.json(summary["tableros"]),
            "charts": summary["charts"],
            "written": MetadataValue.json(summary["escritos"]),
            "verification": summary["verificacion"],
        },
        check_results=[AssetCheckResult(check_name="superset_coincide", passed=summary["ok"], severity=AssetCheckSeverity.ERROR,
                                        metadata={"verification": summary["verificacion"],
                                                  "differences": MetadataValue.json(summary["diferencias"])})],
    )


MONTHLY_ASSETS = [raw_yellow_trips, yellow_schema_report, curated_yellow_trips, warehouse_raw_yellow_trips,
                  warehouse_raw_yellow_quarantine, warehouse_raw_quality]
RAW_SOURCE_KEYS = [AssetKey(["raw", "yellow_trips"]), AssetKey(["raw", "yellow_quarantine"]), AssetKey(["raw", "taxi_zones"])]
ALL_ASSETS = [taxi_zone_lookup, *MONTHLY_ASSETS, warehouse_raw_taxi_zones, dbt_models, resultados_md, superset_dashboards,
              superset_respaldo]
RESOURCES = {"dbt": DbtCliResource(project_dir=DBT_PROJECT, profiles_dir=str(DBT_DIR), target=_target(),
                                   dbt_executable=DBT_EXE)}

defs = Definitions(
    assets=ALL_ASSETS,
    resources=RESOURCES,
    jobs=[
        define_asset_job("monthly_pipeline", AssetSelection.assets(*MONTHLY_ASSETS),
                         description="ingest -> schema -> quality -> load for one month"),
        define_asset_job("reference_data", AssetSelection.assets(taxi_zone_lookup, warehouse_raw_taxi_zones)),
        define_asset_job("warehouse_models", AssetSelection.assets(dbt_models, resultados_md, superset_dashboards, superset_respaldo),
                         description="dbt build + results/YYYY/RESULTS_MM.md + Superset dashboards"),
    ],
)


def register_months(instance: DagsterInstance, labels: list[str]) -> None:
    """Adds the processed months as partitions of the monthly assets (idempotent)."""
    new = [label for label in labels if not instance.has_dynamic_partition(MONTHLY.name, label)]
    if new:
        instance.add_dynamic_partitions(MONTHLY.name, new)


def check_months(mes: str) -> list[Month] | None:
    """The two months of MES, or None (after saying why) when they cannot be compared: MES older than
    2010-01, in the future, or not published by the TLC yet (asked to the TLC CDN, unless the month was
    already ingested in this DATA_DIR)."""
    settings = _settings()
    try:
        months = months_for(mes)
    except ValueError as exc:
        print(f"Cannot run MES={mes}: {exc}", file=sys.stderr)
        _say_why_in_the_report(settings, mes)
        return None
    log = IngestionLog(settings)
    for month in months:
        if log.last_ok("yellow", month.label):
            continue
        if month_published(month) is False:
            print(f"Cannot run MES={mes}: the TLC has not published {month} yet "
                  f"({YELLOW_URL_TEMPLATE.format(mes=month.label)} does not exist). It publishes each month about two "
                  "months after it ends.", file=sys.stderr)
            resultados.write_unavailable(settings, months[0], f"la TLC todavía no publicó {resultados.interp.mes_es(month)} (publica cada "
                                         "mes unos dos meses después de que termina)")
            return None
    return months


def _say_why_in_the_report(settings: Settings, mes: str) -> None:
    """A real month that cannot be compared gets a report without figures that says why. A typo (2025-13), a year the TLC
    never published or one that has not started gets only the message."""
    try:
        month = Month.parse(mes)
    except ValueError:
        return
    today = datetime.now(timezone.utc)
    if FIRST_TLC_MONTH <= month and month.comparison < FIRST_TLC_MONTH:
        reason = (f"los archivos de la TLC empiezan en {resultados.interp.mes_es(FIRST_TLC_MONTH)}, así que no existe "
                  f"{resultados.interp.mes_es(month.comparison)} para comparar")
    elif month.year == today.year and month.month > today.month:
        reason = f"{resultados.interp.mes_es(month)} todavía no empezó"
    else:
        return
    resultados.write_unavailable(settings, month, reason)


def run(mes: str) -> int:
    """make all: zones, each month (partition), zones load, dbt + questions, dashboards. One Dagster run each."""
    months = check_months(mes)
    if months is None:
        return 2
    storage = dagster_instance.configure()
    instance = DagsterInstance.get()
    register_months(instance, [m.label for m in months])
    # Grafana shows the months of this comparison: Pushgateway groups of other months are removed.
    observability.keep_only_months([m.label for m in months])
    os.environ["DBT_MONTHS"] = ",".join(m.label for m in months)
    os.environ["MES"] = mes
    dagster_url = f"http://localhost:{os.environ.get('DAGSTER_UI_PORT', '').strip() or '3003'}"
    ui = dagster_url if storage == "postgres" else f"`make dagster-ui` ({dagster_url})"
    mes_config = {"config": {"mes": mes}}

    def step(selection: list | AssetSelection, partition_key: str | None = None, run_config: dict | None = None) -> bool:
        chosen = selection if isinstance(selection, AssetSelection) else AssetSelection.assets(*selection)
        result = materialize(ALL_ASSETS, selection=chosen, partition_key=partition_key, instance=instance,
                             resources=RESOURCES, run_config=run_config, raise_on_error=False,
                             tags={"mes": mes})
        return result.success

    # The dbt tests on the RAW sources are asset checks of the warehouse assets, but they run inside
    # `dbt build`: they belong to the dbt step (selected there, so Dagster expects their results) and are
    # left out of the load steps (otherwise each load would start dbt again just for them).
    raw_checks = AssetSelection.checks_for_assets(*RAW_SOURCE_KEYS)
    monthly = AssetSelection.assets(*MONTHLY_ASSETS).without_checks() | AssetSelection.checks_for_assets(curated_yellow_trips)
    zones_load = AssetSelection.assets(warehouse_raw_taxi_zones).without_checks()
    models = AssetSelection.assets(dbt_models, resultados_md) | raw_checks

    def dashboards_step() -> bool:
        if not dashboards.superset_expected():
            print(f"Superset is not running ({dashboards.superset_url()}): dashboards skipped, and the report says its figures were "
                  "not compared with Superset yet. Start the stack with `docker compose up -d` and run "
                  f"`make superset-dashboards {evidencia.argumentos_make(_settings(), months[0])}`.", file=sys.stderr)
            return True
        return step([superset_dashboards, superset_respaldo],
                    run_config={"ops": {"superset_dashboards": mes_config, "superset_respaldo": mes_config}})

    plan = [(lambda: step([taxi_zone_lookup]))]
    plan += [(lambda m=m: step(monthly, partition_key=m.label)) for m in months]
    plan += [
        lambda: step(zones_load),
        lambda: step(models, run_config={"ops": {"resultados_md": mes_config}}),
        dashboards_step,
    ]
    for action in plan:
        if not action():
            print(f"Dagster run failed: open {ui} (Runs) for the step logs.", file=sys.stderr)
            return 1
    report = resultados.results_file(months[0])
    print(f"Pipeline finished for {', '.join(m.label for m in months)}. Results (Spanish): {report.relative_to(ROOT).as_posix()}")
    print(f"Evidence dashboards: {evidencia.url_tablero(dashboards.superset_public_url(), evidencia.slug_mes(_settings(), months[0]))} "
          f"and {evidencia.slug_anio(_settings(), months[0].year)} (12 months). {evidencia.estado_verificacion(report)}")
    _print_stack_status()
    return 0


def run_year(year: int) -> int:
    """make all-year: the 12 months of the year, each one a complete `make all` in its own process (its own RUN_ID). A month
    that cannot run yet (future, not published) is reported and skipped; a failed month does not stop the others."""
    codes: dict[str, int] = {}
    env = {k: v for k, v in os.environ.items() if k not in {"RUN_ID", "MES", "DBT_MONTHS"}}
    for number in range(1, 13):
        label = Month(year, number).label
        print(f"=== {label} ({number}/12)", flush=True)
        codes[label] = subprocess.call([sys.executable, "-m", "src.orchestration", "--mes", label], cwd=ROOT, env=env)
    done = [m for m, code in codes.items() if code == 0]
    skipped = [m for m, code in codes.items() if code == 2]
    failed = [m for m, code in codes.items() if code not in (0, 2)]
    print(f"Year {year}: {len(done)} months compared ({', '.join(done) or '-'}); without data yet: {', '.join(skipped) or '-'}; "
          f"failed: {', '.join(failed) or '-'}")
    return 1 if failed or not done else 0


def _print_stack_status() -> None:
    """Where to look now, and whether each UI really answers (a UI that does not is explained by make status)."""
    from src import stack_status

    try:
        statuses = stack_status.check_all()
    except Exception:  # noqa: BLE001 - Docker not installed or not running: the pipeline itself succeeded
        if Path("/.dockerenv").exists():
            # The pipeline container of docker compose has no docker CLI, and the stack is up by definition.
            print("Open the UIs in your browser (`docker compose ps` on the host shows the containers):")
            for service in stack_status.SERVICES:
                if service.name in {"dagster", "grafana", "superset", "prometheus", "dozzle"}:
                    print(f"  {service.title:11s} {service.url}")
            return
        print("Docker stack not running: start it with `docker compose up -d` to see Dagster, Grafana and Superset.")
        return
    for status in statuses:
        if status.service.name in {"dagster", "grafana", "superset", "prometheus", "dozzle"}:
            mark = "OK  " if status.ok else "FAIL"
            print(f"  {mark} {status.service.title:11s} {status.service.url}  {'' if status.ok else status.state}")
    if not all(s.ok for s in statuses):
        print("Some services are not answering: run `make status` to see why and how to fix it.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--mes", help="assigned month YYYY-MM")
    scope.add_argument("--anio", type=int, help="the 12 months of this year, one run each")
    args = parser.parse_args(argv)
    return run_year(args.anio) if args.anio is not None else run(args.mes)


if __name__ == "__main__":
    sys.exit(main())
