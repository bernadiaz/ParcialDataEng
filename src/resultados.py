"""Preguntas de negocio → RESULTADOS.md (stub Paso 1)."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta q1-q6 y escribe RESULTADOS.md")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    print(f"[stub] resultados --mes {args.mes}: pendiente Paso 6.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
