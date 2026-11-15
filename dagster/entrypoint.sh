#!/bin/sh
# Dagster UI container: dagster/supervise.py points the instance at the Postgres of docker compose (the
# history that `make all` writes from the host), serves the UI read only on port 3003 and restarts it
# when the mounted code changes. MES (default 2025-01) and its comparison month are registered as
# partitions, so a new UI shows every asset grey until `make all` materializes it.
set -eu
exec python /opt/nyc_taxi/dagster/supervise.py
