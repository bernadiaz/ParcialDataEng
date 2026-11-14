# Orquestación del pipeline NYC Taxi.
# Uso típico (Docker + ambiente):
#   make up ENV=dev
#   make all ENV=dev MES=2025-03
#   make down ENV=dev

SHELL := /bin/bash
.DEFAULT_GOAL := help

ENV       ?= dev
MES       ?= 2025-03
ENV_FILE  := environments/$(ENV).env
DOTENV    := $(shell test -f .env && echo --env-file .env)
COMPOSE   := docker compose -f docker/docker-compose.yml $(DOTENV)
PROFILE   := --profile $(ENV)

# Carga .env del repo si existe (secretos) + archivo de ambiente
export ENV MES
-include .env
export

.PHONY: help install up down logs shell \
	ingest schema quality load-sf dbt-run questions all test \
	demo-idempotency show-quarantine quality-report clean

help: ## Muestra targets disponibles
	@echo "ENV=$(ENV)  MES=$(MES)"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z_-]+:.*## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Instala deps en el host (opcional; preferir Docker)
	python3 -m pip install -e ".[dev]"

up: ## Prepara ambiente (dev fs: dirs; dev s3: MinIO Docker si hay imagen)
	@test -f .env || cp .env.example .env
	@mkdir -p data/raw/yellow data/raw/zones data/control data/object_store
	@if [ "$${OBJECT_STORE:-fs}" = "s3" ] || grep -q '^OBJECT_STORE=s3' environments/$(ENV).env 2>/dev/null; then \
		echo "OBJECT_STORE=s3 → levantando MinIO…"; \
		$(COMPOSE) $(PROFILE) up -d minio minio-init; \
		echo "MinIO listo. Consola http://localhost:9001"; \
	else \
		echo "OBJECT_STORE=fs → data/object_store listo (sin MinIO; ideal 8 GB)."; \
		echo "Para MinIO: OBJECT_STORE=s3 make up ENV=$(ENV)"; \
	fi

down: ## Baja contenedores del ambiente
	$(COMPOSE) $(PROFILE) down

logs: ## Logs de servicios Docker
	$(COMPOSE) $(PROFILE) logs -f --tail=100

shell: ## Shell dentro del worker del pipeline
	$(COMPOSE) $(PROFILE) run --rm --entrypoint bash pipeline

# --- Etapas del pipeline (ejecutan DENTRO de Docker) ---

_run = $(COMPOSE) $(PROFILE) run --rm --entrypoint "" \
	-e ENV=$(ENV) -e MES=$(MES) \
	--env-file $(ENV_FILE) \
	pipeline

ingest: ## Parte 1: ingesta (mes + mes 2024 + zonas) vía Docker
	$(_run) python -m src.ingesta_airbyte --mes $(MES)

ingest-host: ## Ingesta en el host con .venv (sin build Docker)
	@test -f .env || cp .env.example .env
	@test -x .venv/bin/python || (echo "Creá .venv: uv venv && uv pip install -e '.[dev]'"; exit 1)
	ENV=$(ENV) MES=$(MES) .venv/bin/python -m src.ingesta_airbyte --mes $(MES)

schema: ## Parte 2: contrato de esquema + normalización (Docker)
	$(_run) python -m src.esquema --mes $(MES)

schema-host: ## Esquema en el host con .venv
	@test -x .venv/bin/python || (echo "Falta .venv"; exit 1)
	ENV=$(ENV) MES=$(MES) .venv/bin/python -m src.esquema --mes $(MES)

quality: ## Parte 3: calidad, cuarentena, reconciliación
	$(_run) python -m src.calidad --mes $(MES)

load-sf: ## Parte 4a: carga a Snowflake (skip en ENV=dev por defecto)
	$(_run) python -m src.load_snowflake --mes $(MES)

dbt-run: ## Parte 4b-5: dbt transform + modelo estrella
	$(_run) bash -c 'if [ "$${SKIP_DBT:-0}" = "1" ]; then echo "[skip] dbt (SKIP_DBT=1)"; else cd dbt_taxi && dbt run --vars "{\"mes\": \"$(MES)\"}"; fi'

questions: ## Parte 5: preguntas de negocio → RESULTADOS.md
	$(_run) python -m src.resultados --mes $(MES)

all: ## Pipeline completo: ingest→schema→quality→load→dbt→questions
	@echo "==> all ENV=$(ENV) MES=$(MES)"
	@$(MAKE) ingest ENV=$(ENV) MES=$(MES)
	@$(MAKE) schema ENV=$(ENV) MES=$(MES)
	@$(MAKE) quality ENV=$(ENV) MES=$(MES)
	@$(MAKE) load-sf ENV=$(ENV) MES=$(MES)
	@$(MAKE) dbt-run ENV=$(ENV) MES=$(MES)
	@$(MAKE) questions ENV=$(ENV) MES=$(MES)
	@echo "==> done"

test: ## Tests automatizados (pytest)
	$(_run) pytest -q

demo-idempotency: ## Defensa: re-correr ingest y mostrar log
	@$(MAKE) ingest ENV=$(ENV) MES=$(MES)
	@$(MAKE) ingest ENV=$(ENV) MES=$(MES)
	$(_run) python -c "from pathlib import Path; p=Path('data/control/ingestion_log.csv'); print(p.read_text() if p.exists() else 'log aun no generado')"

show-quarantine: ## Defensa: muestra muestra de cuarentena
	$(_run) python -c "import duckdb; c=duckdb.connect(); print(c.execute(\"select * from read_parquet('data/quarantine/**/*.parquet') limit 5\").df())"

quality-report: ## Defensa: imprime reporte de calidad del mes
	@ls -la data/reports/ 2>/dev/null || echo "Aun no hay reportes (correr make quality)"

clean: ## Limpia artefactos locales (no toca S3/MinIO)
	rm -rf data/staging data/curated data/quarantine data/reports data/control/*.csv
	@echo "Limpieza local ok. Raw en object store intacto."
