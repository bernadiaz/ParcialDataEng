"""Carga DuckDB → Snowflake (stub Paso 1). Skip automático en ENV=dev."""

from __future__ import annotations

import argparse
import sys

from src.config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga a Snowflake")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    settings = get_settings(mes=args.mes)
    if settings.skip_snowflake:
        print(f"[skip] load_snowflake (SKIP_SNOWFLAKE=1, ENV={settings.env})")
        return 0
    print(f"[stub] load_snowflake --mes {args.mes}: pendiente paso posterior.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
