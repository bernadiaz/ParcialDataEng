"""Runs dbt or the Dagster UI with the environment prepared by src/config.py.

src/config.py loads .env and expands the portable paths (~ and relative paths) for this OS. It also
derives DAGSTER_HOME and DUCKDB_WAREHOUSE_PATH from DATA_DIR. Running the tools through this module
keeps the Makefile free of OS-specific paths.

    python -m src.run_tool dbt build --project-dir dbt_taxi --profiles-dir dbt_taxi --target duckdb
    python -m src.run_tool dagster-ui 3003
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

from src import config  # side effect: .env loaded, paths normalized


def _executable(name: str) -> str:
    """The tool installed in this virtual environment (Scripts\\ on Windows, bin/ elsewhere)."""
    candidate = Path(sys.executable).with_name(name + (".exe" if os.name == "nt" else ""))
    return str(candidate) if candidate.exists() else name


def _port_in_use(port: int) -> bool:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
        return True
    except OSError:
        return False


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"dbt", "dagster-ui"}:
        print("usage: python -m src.run_tool dbt <args...> | dagster-ui [port]", file=sys.stderr)
        return 2
    if argv[0] == "dbt":
        args = argv[1:]
        if "--target" not in args and "-t" not in args and args and args[0] not in {"--version", "deps", "clean"}:
            args += ["--target", config.dbt_target()]  # same rule as make all (src/config.py)
        return subprocess.call([_executable("dbt"), *args])
    port = argv[1] if len(argv) > 1 else "3003"
    if _port_in_use(int(port)):
        # docker compose already serves the Dagster UI there, on the same run history as make all.
        print(f"The Dagster UI is already running at http://localhost:{port} (docker compose): open it in the browser.")
        return 0
    from src import dagster_instance

    Path(os.environ["DAGSTER_HOME"]).mkdir(parents=True, exist_ok=True)
    dagster_instance.configure()
    return subprocess.call([_executable("dagster"), "dev", "-m", "src.orchestration", "-p", port])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
