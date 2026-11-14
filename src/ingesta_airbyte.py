"""Parte 1 — Ingesta (stub Paso 1).

Implementación completa en Paso 2:
- Descarga TLC → S3/MinIO path Hive year=/month=/
- Idempotencia por hash
- ingestion_log
- Reintentos x3
- Opcional: trigger Airbyte si AIRBYTE_ENABLED=true
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingesta NYC Yellow Taxi")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    print(
        f"[stub] ingest --mes {args.mes}: pendiente Paso 2 "
        "(descarga idempotente + MinIO/S3 + ingestion_log)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
