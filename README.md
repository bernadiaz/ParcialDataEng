# Pipeline NYC Taxi (examen)

Pipeline batch reproducible: **ingesta → esquema → calidad → carga → dbt → preguntas**.

Stack (según plan): **Airbyte → S3 → DuckDB (calidad) → Snowflake + dbt**, orquestado con `make all MES=YYYY-MM`.

Todo corre **dockerizado**, con ambientes **`dev`** / **`prod`**, pensado para una máquina de **~8 GB RAM**.

## Ambientes

| | `ENV=dev` (default) | `ENV=prod` |
|---|---|---|
| Object store | **MinIO** en Docker (S3 API) | **AWS S3** real |
| Ingesta | Cliente ligero Python (mismos paths que Airbyte) | Airbyte sync o mismo cliente |
| Calidad / esquema | DuckDB en contenedor (`memory_limit=2GB`) | Igual |
| Warehouse | Skip Snowflake/dbt (`SKIP_*=1`) — marts locales más adelante si hace falta | **Snowflake** + **dbt** |
| Memoria Docker | MinIO ≤512 MB + worker ≤3 GB | Solo worker ≤3 GB |

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

- `cbd_congestion_fee` en 2024 → **NULL** (no 0).
- Columna nueva no contratada → ignore + warning; requerida faltante → falla.
- Distancia máxima: candidato **100 mi** (se confirma tras exploración).
- FinOps Snowflake: warehouse XS, auto-suspend 60s, staging transient, `fact_trips` incremental por mes (detalle al cablear dbt).

## Estado de implementación

| Paso | Contenido | Estado |
|------|-----------|--------|
| 1 | Scaffold Docker + ambientes + estructura | **listo** |
| 2 | Ingesta idempotente + log | pendiente |
| 3 | Esquema + normalización | pendiente |
| 4 | Calidad + cuarentena | pendiente |
| 5 | Transform / dbt / estrella | pendiente |
| 6 | Preguntas + tests + docs finales | pendiente |

## Declaración de uso de IA

Asistente: **Cursor**. Uso: scaffolding del repo, Docker/ambientes, estructura alineada al plan y a la consigna. El código de cada etapa se revisa y se debe poder explicar en la defensa oral. Commits sin `Co-authored-by` de Cursor.

## Limitaciones conocidas (Paso 1)

- Módulos de pipeline aún son stubs (el `make all` corre el esqueleto sin bajar datos).
- Airbyte OSS no se levanta en Compose (RAM); en `dev` se emula el destino S3 con MinIO.
- Tiempo de ejecución / pico de RAM: se documentan tras la primera corrida real.
