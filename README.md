# Pipeline NYC Taxi (examen)

Pipeline batch reproducible: **ingesta → esquema → calidad → carga → dbt → preguntas**.

Stack (según plan): **Airbyte → S3 → DuckDB (calidad) → Snowflake + dbt**, orquestado con `make all MES=YYYY-MM`.

Todo corre **dockerizado**, con ambientes **`dev`** / **`prod`**, pensado para una máquina de **~8 GB RAM**.

## Ambientes

| | `ENV=dev` (default) | `ENV=prod` |
|---|---|---|
| Object store | **`OBJECT_STORE=fs`** → `data/object_store/` (sin MinIO; 8 GB) | **AWS S3** (`OBJECT_STORE=s3`) |
| Alternativa | `OBJECT_STORE=s3` + MinIO en Docker (si el registry responde) | — |
| Ingesta | Cliente HTTP ligero (mismos paths Hive que Airbyte) | Airbyte sync o mismo cliente |
| Calidad / esquema | DuckDB (`memory_limit=2GB`) | Igual |
| Warehouse | Skip Snowflake/dbt (`SKIP_*=1`) | **Snowflake** + **dbt** |

Secretos: copiá `.env.example` → `.env` (nunca se versiona).  
Config no secreta: `environments/dev.env` y `environments/prod.env`.

## Requisitos

- Docker + Docker Compose v2 (**daemon en marcha**: `sudo systemctl start docker`)
- ~8 GB RAM libres recomendados (límites en `docker/docker-compose.yml`)
- Credenciales AWS + Snowflake solo para `ENV=prod`

## Instalación y ejecución

```bash
cp .env.example .env
# opcional: editar .env

# 1) Infra local (MinIO)
make up ENV=dev

# 2) Pipeline completo (mes asignado + mismo mes 2024)
make all ENV=dev MES=2025-03
```

Comandos por etapa: `make ingest|schema|quality|load-sf|dbt-run|questions MES=...`.

Tests: `make test ENV=dev`.

## Arquitectura (resumen)

```
TLC HTTPS ──► [ingesta] ──► S3/MinIO raw/yellow/year=/month=/
                              │
                              ▼
                         DuckDB esquema + calidad
                              │
                    aceptadas / cuarentena / reportes
                              │
                    (prod) Snowflake RAW/STAGING
                              │
                         dbt marts (estrella)
                              │
                         sql/q1..q6 → RESULTADOS.md
```

Detalle Airbyte: [`airbyte/README_AIRBYTE.md`](airbyte/README_AIRBYTE.md).  
Contrato de columnas: [`contracts/yellow_schema.yaml`](contracts/yellow_schema.yaml).

## Decisiones clave (parcial — se completa al implementar)

- `cbd_congestion_fee` en 2024 → **NULL** (no 0): distingue “sin columna / sin dato” de “fee cobrado = 0” en 2025.
- Columna nueva no contratada (p.ej. `month`/`year` del Parquet TLC) → **ignore + warning** en `data/reports/schema_report_*.md`.
- Columna requerida faltante → **falla** el pipeline.
- Destino tipado en `contracts/yellow_schema.yaml`; el código solo aplica aliases + CAST.
- Distancia máxima: candidato **100 mi** (se confirma tras exploración).
- FinOps Snowflake: warehouse XS, auto-suspend 60s, staging transient, `fact_trips` incremental por mes (detalle al cablear dbt).

## Estado de implementación

| Paso | Contenido | Estado |
|------|-----------|--------|
| 1 | Scaffold Docker + ambientes + estructura | **listo** |
| 2 | Ingesta idempotente + log | **listo** |
| 3 | Esquema + normalización | **listo** |
| 4 | Calidad + cuarentena | pendiente |
| 5 | Transform / dbt / estrella | pendiente |
| 6 | Preguntas + tests + docs finales | pendiente |

## Declaración de uso de IA

Asistente: **Cursor**. Uso: scaffolding del repo, Docker/ambientes, estructura alineada al plan y a la consigna. El código de cada etapa se revisa y se debe poder explicar en la defensa oral. Commits sin `Co-authored-by` de Cursor.

## Ingesta (Paso 2)

- Destino local (consigna): `data/raw/yellow/year=AAAA/month=MM/` + `data/raw/zones/`
- Object store (mismos keys Hive):
  - `OBJECT_STORE=fs` (default `dev`) → `data/object_store/...`
  - `OBJECT_STORE=s3` (`prod` / opcional) → MinIO o AWS S3
- Comparación automática: mismo mes del año anterior
- Idempotencia por SHA-256 (local + store + `ingestion_log`)
- Reintentos de red: 3 (1s / 2s / 4s); falla → `estado=error` y exit ≠ 0
- Log: `data/control/ingestion_log.csv`

```bash
make up ENV=dev
make ingest-host ENV=dev MES=2025-03   # o: make ingest (Docker)
# segunda vez → skipped
make ingest-host ENV=dev MES=2025-03
```

Verificado con `MES=2025-03`: ~4.1M / ~3.6M filas; 2ª corrida en <3s con `estado=skipped`.

## Esquema (Paso 3)

```bash
make schema-host ENV=dev MES=2025-03
```

Salida:
- Staging Hive: `data/staging/yellow/year=*/month=*/part.parquet`
- Reportes: `data/reports/schema_report_YYYY-MM.{md,csv,json}`

## Limitaciones conocidas

- Etapas calidad/dbt/preguntas aún son stubs.
- Airbyte OSS no se levanta en Compose (RAM); en `dev` MinIO + cliente HTTP escriben los mismos paths.
- Tiempo de ejecución / pico de RAM: se documentan tras la primera corrida real con Parquets TLC.
