# Airbyte → S3 (ingesta cloud)

El plan del examen usa **Airbyte** como capa de ingesta hacia S3 (Hive `year=/month=/`).

## Por qué no va en `docker compose` por defecto

Airbyte OSS (abctl / platform) suele pedir **varios GB de RAM**. Este repo debe correr en una notebook de **~8 GB**, así que:

| Ambiente | Ingesta |
|----------|---------|
| `ENV=dev` | Cliente ligero Python (`src/ingesta_airbyte.py`) → **MinIO** (mismos paths que Airbyte) |
| `ENV=prod` | Airbyte sync real → **AWS S3**, o el mismo cliente si `AIRBYTE_ENABLED=false` |

Los paths de destino son idénticos en ambos casos para que DuckDB no cambie.

## Paths destino

```
s3://<bucket>/raw/yellow/year=AAAA/month=MM/yellow_tripdata_AAAA-MM.parquet
s3://<bucket>/raw/zones/taxi_zone_lookup.csv
s3://<bucket>/control/ingestion_log.csv   # o append local en data/control/
```

## Connection (export documentado)

Ver `airbyte/connections/yellow_to_s3.yaml` (plantilla sin secretos).

### Pasos UI (resumen)

1. Source: HTTP files / S3 (URLs TLC Parquet + CSV zonas).
2. Destination: S3 bucket del alumno, path prefix `raw/`.
3. Sync mode: overwrite por path de mes (idempotencia a nivel objeto).
4. Guardar `connection_id` en `.env` (`AIRBYTE_CONNECTION_ID_YELLOW`, `AIRBYTE_CONNECTION_ID_ZONES`).

### Trigger desde Makefile

Con `AIRBYTE_ENABLED=true`, `make ingest` dispara sync vía API y verifica hash post-sync (implementado en Paso 2). Reintentos: 3 con espera 1s / 2s / 4s.

## Fuentes TLC

- Yellow: `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_AAAA-MM.parquet`
- Zonas: [taxi_zone_lookup.csv](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv)
