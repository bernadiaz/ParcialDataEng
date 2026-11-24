"""Kept for older commands: the dashboards are built by src/dashboards.py.

`make all` builds them as the Dagster asset `superset_dashboards`; `make superset-dashboards` runs
them alone.

    python superset/bootstrap_dashboards.py --mes 2025-01
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dashboards import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
