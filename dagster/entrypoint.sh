#!/bin/sh
# Dagster UI container: points the instance at the Postgres of docker compose (the history that
# `make all` writes from the host) and serves the UI read only on port 3003.
set -eu
cd /opt/nyc_taxi
# MES (default 2025-01, the exam month) and its comparison month are registered as partitions, so a
# new UI shows every asset grey until `make all` materializes it.
python -m src.dagster_instance --months "${MES:-2025-01}"
exec dagster-webserver -h 0.0.0.0 -p 3003 -m src.orchestration -d /opt/nyc_taxi --read-only
