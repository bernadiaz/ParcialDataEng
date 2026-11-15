#!/usr/bin/env bash
# First start: metadata database, admin user, roles. Then the normal Superset server.
set -euo pipefail

superset db upgrade
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --firstname NYC --lastname Taxi --email admin@nyc-taxi.local \
    --password "${SUPERSET_ADMIN_PASSWORD}" || true
# .env is the source of truth: if SUPERSET_ADMIN_PASSWORD changed after the first start, apply it, so the
# dashboards step of `make all` (and the login) keep working.
superset fab reset-password \
    --username "${SUPERSET_ADMIN_USER:-admin}" \
    --password "${SUPERSET_ADMIN_PASSWORD}" || true
superset init

exec /usr/bin/run-server.sh
