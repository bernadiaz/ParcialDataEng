# =============================================================================================
# NYC Taxi pipeline - single entry point. `make all` runs the pipeline through Dagster.
#
#   docker compose up -d          Dagster UI, Grafana, Prometheus, Loki, Dozzle, Superset (or: make up)
#   make all MES=2025-01          cloud: ingest -> schema -> quality -> load -> dbt -> questions ->
#                                 Superset dashboards, for MES and the same month of the previous year
#   make all MES=2025-01 INGEST_MODE=direct WAREHOUSE=duckdb      the same, offline (no cloud account)
#   make help                     list every target
#
# `make all` creates .venv and installs the project the first time (and again when pyproject.toml
# changes), so `make install` is optional. Settings and credentials come from .env (see .env.example).
# Paths in .env are portable (~ = home, relative = repo) and are resolved by src/config.py, so this
# Makefile has no machine-specific path. Works on Linux, macOS and Windows (run make from Git Bash).
# =============================================================================================
-include .env
export

MES ?= 2025-01

# Python 3.12 or newer: the first interpreter of the list that qualifies (override with PYTHON=...).
ifeq ($(OS),Windows_NT)
  VENV_BIN := .venv/Scripts
  PY_CANDIDATES := "py -3.12" "py -3.13" "py -3.14" "py -3" python3 python
else
  VENV_BIN := .venv/bin
  PY_CANDIDATES := python3.12 python3.13 python3.14 python3
endif
PYTHON ?= $(shell for c in $(PY_CANDIDATES); do $$c -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1 && { echo "$$c"; break; }; done)
unexport PYTHON PY_CANDIDATES
PY  := $(VENV_BIN)/python
# Written by `make install`; older than pyproject.toml (or missing) = the .venv must be (re)installed.
VENV := .venv/.installed
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

# dbt target (offline DuckDB, Snowflake key pair or browser SSO): chosen by src/config.py, the same rule
# that `make all` uses, and added by src/run_tool.py.
DBT_ARGS = --project-dir dbt_taxi --profiles-dir dbt_taxi

.DEFAULT_GOAL := help
.PHONY: help install all all-steps dagster-ui up down superset-dashboards airbyte-setup airbyte-sync schema \
        quality load-sf dbt-run dbt-docs questions test explore demo-idempotency show-quarantine quality-report \
        finops clean

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*## ' Makefile | sed -E 's/:.*## /\t/' | expand -t 22

install: ## create .venv and install dependencies (Python 3.12+ found automatically, or PYTHON=...)
	@test -n "$(PYTHON)" || { echo "Python 3.12 or newer was not found. Install it (see the run guide) or pass PYTHON=..."; exit 1; }
	$(PYTHON) -m venv --clear .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	@$(PY) -c "open('$(VENV)', 'w').close()"

$(VENV): pyproject.toml
	@echo "Preparing .venv (first run, or pyproject.toml changed)..."
	@$(MAKE) --no-print-directory install

all: $(VENV) ## full pipeline for MES and its comparison month, orchestrated by Dagster (lineage at http://localhost:3003)
	$(PY) -m src.orchestration --mes $(MES)

all-steps: $(VENV) airbyte-sync schema quality load-sf dbt-run questions ## same pipeline, step by step without Dagster (debugging)
	@echo "Pipeline finished for $(MONTHS) (run $(RUN_ID))"

dagster-ui: $(VENV) ## Dagster UI on http://localhost:3003 (already served by docker compose when the stack is up)
	$(PY) -m src.run_tool dagster-ui 3003

up: ## start the Dagster UI, Grafana, Prometheus, Pushgateway, Loki, Alloy, Dozzle and Superset (docker compose)
	docker compose up -d --build

down: ## stop the docker compose stack (volumes are kept)
	docker compose down

superset-dashboards: $(VENV) ## create/update the Superset dashboards alone (make all already does it)
	$(PY) -m src.dashboards --mes $(MES)

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

test: $(VENV) ## pytest on synthetic data (no cloud account needed)
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

clean: $(VENV) ## empty DATA_DIR, the Dagster history and the dbt artifacts (keeps .env, .venv and the Superset dashboards)
	$(PY) -m src.clean
