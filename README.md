# Pipeline NYC Taxi (examen)

Pipeline batch reproducible: **ingesta → esquema → calidad → transform → modelo → preguntas**.

Stack: cliente HTTP (paths tipo Airbyte) → object store → **DuckDB** (esquema/calidad/curated/marts) → opcional **Snowflake + dbt** en `prod`. Orquestación: `make all MES=YYYY-MM` / `make all-host`.

Todo pensado para **~8 GB RAM**, con ambientes **`dev`** / **`prod`**.

## Ambientes

| | `ENV=dev` (default) | `ENV=prod` |
|---|---|---|
| Object store | `OBJECT_STORE=fs` → `data/object_store/` | AWS S3 (`OBJECT_STORE=s3`) |
| Warehouse analítico | DuckDB `data/warehouse/nyc_taxi.duckdb` | Snowflake + dbt |
| DuckDB | `memory_limit=2GB`, `threads=2` | igual (calidad local previa) |

Secretos: `.env` (desde `.env.example`). Config: `environments/dev.env`, `environments/prod.env`.

## Requisitos

- Python 3.12+ (se probó con 3.14 + `uv`)
- ~8 GB RAM
- Docker opcional (Compose para MinIO/`make all`); en notebook: `make all-host`
- Credenciales AWS/Snowflake solo para `ENV=prod`

## Instalación y ejecución

```bash
cp .env.example .env
uv venv .venv
uv pip install duckdb pyyaml boto3 httpx python-dotenv pytest
# (prod) también: dbt-snowflake

make up ENV=dev
make all-host ENV=dev MES=2025-03
```

Etapas sueltas:

```bash
make ingest-host schema-host quality-host transform-host model-host questions-host MES=2025-03
```

Tests: `.venv/bin/python -m pytest -q`  
Defensa: `make demo-idempotency`, `make quality-report`, `make show-quarantine`.

## Arquitectura

```
TLC HTTPS ──► ingesta ──► data/raw + object_store (Hive year=/month=/)
                              │
                         DuckDB esquema → staging
                              │
                         calidad → accepted / quarantine + reports
                              │
                         transform → curated (derivados + zonas)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            DuckDB marts (dev)    Snowflake+dbt (prod)
                    │
              sql/q* → RESULTADOS.md
```

## Decisiones

- `cbd_congestion_fee` en 2024 → **NULL** (no 0).
- Columna nueva no contratada → ignore + warning; requerida faltante → falla.
- Distancia máxima **100 mi** (P99≈19.7, P99.9≈29 en muestra 2024-03+2025-03).
- R05/R08 = warn; R01–R04, R06–R07, R09 = reject (R09: duración > 8 h).
- Reproceso de mes: replace solo su partición curated (ver `data/reports/partition_replace_*.md`).
- FinOps (prod): warehouse XS, auto-suspend 60s, staging transient, `fact_trips` incremental.

### Granularidad del modelo

| Tabla | Granularidad |
|-------|----------------|
| `marts.dim_zone` | 1 fila / LocationID |
| `marts.dim_date` | 1 fila / fecha pickup |
| `marts.fact_trips` | 1 fila / viaje curado |
| `marts.agg_zone_hour` | zona origen × fecha × hora |

## Cómo mirar los datos

| Qué | Dónde |
|-----|--------|
| Reportes | `data/reports/*.md` |
| Log ingesta | `data/control/ingestion_log.csv` |
| Parquets | `data/raw`, `staging`, `accepted`, `quarantine`, `curated` |
| Modelo | `data/warehouse/nyc_taxi.duckdb` → **DataGrip/DBeaver (DuckDB)** |
| Respuestas negocio | `RESULTADOS.md` |

pgAdmin no aplica (no hay Postgres).

## Preguntas (Paso 6)

```bash
make questions-host ENV=dev MES=2025-03
```

SQL versionado en `sql/q1_…` … `q6_…` (+ `q3b_…`). Salida: `RESULTADOS.md`.

## Rendimiento observado (máquina de desarrollo, `MES=2025-03`)

| Etapa | Orden de magnitud |
|-------|-------------------|
| Ingesta (2 Parquets + zonas) | ~40–60 s red |
| Esquema | ~10 s |
| Calidad | ~45–50 s |
| Transform (×2 si reproceso) | ~20–40 s |
| Modelo DuckDB | ~1–2 min |
| Pico DuckDB | `memory_limit=2GB` configurado |

## Estado

| Paso | Estado |
|------|--------|
| 1 Scaffold Docker + ambientes | listo |
| 2 Ingesta idempotente | listo |
| 3 Esquema | listo |
| 4 Calidad + cuarentena | listo |
| 5 Transform + estrella | listo |
| 6 Preguntas + docs | listo |

## Declaración de uso de IA

Asistente: **Cursor**. Uso: scaffold, Docker/ambientes, módulos de pipeline, SQL de preguntas y documentación alineada al plan/consigna. El código debe poder explicarse en la defensa; commits sin `Co-authored-by` de Cursor.

## Limitaciones

- Airbyte OSS no se levanta en Compose (RAM); `dev` usa cliente HTTP + `OBJECT_STORE=fs`.
- Snowflake/dbt solo con `ENV=prod` y credenciales.
- Interpretaciones en `RESULTADOS.md` son borrador para oral: conviene personalizarlas.
- Imágenes MinIO en Docker Hub pueden fallar según registry; por eso el default `fs`.
