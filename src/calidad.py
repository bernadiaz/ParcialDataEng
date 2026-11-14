"""Parte 3 — Calidad y cuarentena (stub Paso 1). Implementación en Paso 4."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calidad de datos Yellow Taxi")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    print(f"[stub] calidad --mes {args.mes}: pendiente Paso 4.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
