"""Runs dbt or the Dagster UI with the environment prepared by src/config.py.

src/config.py loads .env and expands the portable paths (~ and relative paths) for this OS. It also
derives DAGSTER_HOME and DUCKDB_WAREHOUSE_PATH from DATA_DIR. Running the tools through this module
keeps the Makefile free of OS-specific paths.

    python -m src.run_tool dbt build --project-dir dbt_taxi --profiles-dir dbt_taxi --target duckdb
    python -m src.run_tool dagster-ui 3003
"""
import os
import subprocess
import sys
from pathlib import Path

from src import config  # noqa: F401  (side effect: .env loaded, paths normalized)


def _executable(name: str) -> str:
    """The tool installed in this virtual environment (Scripts\\ on Windows, bin/ elsewhere)."""
    candidate = Path(sys.executable).with_name(name + (".exe" if os.name == "nt" else ""))
    return str(candidate) if candidate.exists() else name


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"dbt", "dagster-ui"}:
        print("usage: python -m src.run_tool dbt <args...> | dagster-ui [port]", file=sys.stderr)
        return 2
    if argv[0] == "dbt":
        return subprocess.call([_executable("dbt"), *argv[1:]])
    Path(os.environ["DAGSTER_HOME"]).mkdir(parents=True, exist_ok=True)
    port = argv[1] if len(argv) > 1 else "3003"
    return subprocess.call([_executable("dagster"), "dev", "-m", "src.orchestration", "-p", port])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
