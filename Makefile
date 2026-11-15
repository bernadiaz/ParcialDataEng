# =============================================================================================
# NYC Taxi pipeline - single entry point. `make all` runs the pipeline through Dagster.
#
#   make install                  create .venv and install the project (Python 3.12+)
#   make up                       observability + BI stack (Grafana, Prometheus, Loki, Dozzle, Superset)
#   make all MES=2025-01          ingest -> schema -> quality -> load -> dbt -> questions
#                                 for MES and the same month of the previous year (Dagster)
#   make superset-dashboards      business dashboards in Superset
#   make help                     list every target
#
# Settings and credentials come from .env (see .env.example). Paths in .env are portable (~ = home,
# relative = repo) and are resolved by src/config.py, so this Makefile has no machine-specific path.
# Works on Linux, macOS and Windows (run make from Git Bash).
# =============================================================================================
-include .env
export

MES ?= 2025-01

ifeq ($(OS),Windows_NT)
  VENV_BIN := .venv/Scripts
  PYTHON ?= py -3.12
else
  VENV_BIN := .venv/bin
  PYTHON ?= python3.12
endif
PY  := $(VENV_BIN)/python
# dbt and the Dagster UI run through src/run_tool.py, which resolves the paths of .env first.
DBT := $(PY) -m src.run_tool dbt

# One RUN_ID for every step of this make invocation (lineage in logs, reports and load_log).
ifndef RUN_ID
  RUN_ID := $(shell $(PY) -m src.config run-id 2>/dev/null)
endif
export RUN_ID

# MES and its comparison month, e.g. "2025-01 2024-01" (computed by src/config.py).
MONTHS = $(shell $(PY) -m src.config months $(MES))
MES_ARGS = $(foreach m,$(MONTHS),--mes $(m))
comma := ,
empty :=
space := $(empty) $(empty)
export DBT_MONTHS = $(subst $(space),$(comma),$(strip $(MONTHS)))

# dbt target: offline DuckDB, Snowflake key pair (service user) or Snowflake browser SSO.
ifeq ($(WAREHOUSE),duckdb)
  DBT_TARGET ?= duckdb
else ifneq ($(strip $(SNOWFLAKE_PRIVATE_KEY_PATH)),)
  DBT_TARGET ?= snowflake_keypair
else
  DBT_TARGET ?= snowflake_browser
endif
export DBT_TARGET
DBT_ARGS = --project-dir dbt_taxi --profiles-dir dbt_taxi --target $(DBT_TARGET)

.DEFAULT_GOAL := help
.PHONY: help install all all-steps dagster-ui up down superset-dashboards airbyte-setup airbyte-sync schema \
        quality load-sf dbt-run dbt-docs questions test explore demo-idempotency show-quarantine quality-report \
        finops clean

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*## ' Makefile | sed -E 's/:.*## /\t/' | expand -t 22

install: ## create .venv and install dependencies (override the interpreter with PYTHON=...)
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

all: ## full pipeline for MES and its comparison month, orchestrated by Dagster (runs visible in make dagster-ui)
	$(PY) -m src.orchestration --mes $(MES)

all-steps: airbyte-sync schema quality load-sf dbt-run questions ## same pipeline, step by step without Dagster (debugging)
	@echo "Pipeline finished for $(MONTHS) (run $(RUN_ID))"

dagster-ui: ## Dagster UI on http://localhost:3003 (asset lineage, partitions, runs, reconciliation checks)
	$(PY) -m src.run_tool dagster-ui 3003

up: ## start Prometheus, Pushgateway, Grafana, Loki, Alloy, Dozzle and Superset (docker compose)
	docker compose up -d --build

down: ## stop the docker compose stack (volumes are kept)
	docker compose down

superset-dashboards: ## create/update the Superset dashboards (English) for MES vs the same month last year
	$(PY) superset/bootstrap_dashboards.py --mes $(MES)

airbyte-setup: ## optional: create the Airbyte objects ahead of time (ingestion creates them automatically)
	$(PY) -m src.ingesta_airbyte --setup --mes $(MES)

airbyte-sync: ## land the TLC files in S3 with Airbyte, verify SHA-256, write ingestion_log
	$(PY) -m src.ingesta_airbyte $(MES_ARGS)

schema: ## compare every raw file with contracts/yellow_schema.yaml
	$(PY) -m src.esquema $(MES_ARGS)

quality: ## quality rules -> curated / quarantine, reports MD+CSV, reconciliation
	$(PY) -m src.calidad $(MES_ARGS)

load-sf: ## load the curated months into the warehouse RAW layer (replaces only those months)
	$(PY) -m src.load_snowflake $(MES_ARGS)

dbt-run: ## dbt build: staging -> intermediate -> marts + tests (incremental by month)
	$(DBT) build $(DBT_ARGS)

dbt-docs: ## generate dbt docs (lineage and model descriptions)
	$(DBT) docs generate $(DBT_ARGS)

questions: ## run sql/q1..q6 against the marts and write RESULTADOS.md
	$(PY) -m src.resultados --mes $(MES)

test: ## pytest on synthetic data (no cloud account needed)
	$(PY) -m pytest

explore: ## distance / speed exploration behind the R03 and R09 thresholds
	$(PY) -m src.exploracion $(MES_ARGS)

demo-idempotency: ## run the whole pipeline again and show that no count changes
	$(PY) -m src.demos counts --label before
	$(MAKE) all MES=$(MES)
	$(PY) -m src.demos counts --label after --compare before

show-quarantine: ## one quarantined row per violated rule (MES)
	$(PY) -m src.demos show-quarantine --mes $(MES)

quality-report: ## print the quality report (MES)
	$(PY) -m src.demos quality-report --mes $(MES)

finops: ## Snowflake credits and query time of this project (by query tag)
	$(PY) -m src.demos finops

clean: ## remove local data (DATA_DIR) and dbt artifacts (keeps .env, .venv and the Superset metadata in DATA_DIR/superset_home)
	$(PY) -c "import shutil; from src.config import Settings; d = Settings.from_env().data_dir; [shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink() for p in (sorted(d.iterdir()) if d.is_dir() else []) if p.name != 'superset_home']; [shutil.rmtree(p, ignore_errors=True) for p in ('dbt_taxi/target', 'dbt_taxi/logs')]"
