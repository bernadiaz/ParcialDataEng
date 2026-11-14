"""Parte 2 — Esquema (stub Paso 1). Implementación en Paso 3."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validación de esquema Yellow Taxi")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    print(f"[stub] esquema --mes {args.mes}: pendiente Paso 3.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
