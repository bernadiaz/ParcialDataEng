#!/bin/sh
# `make` of the pipeline container: docker compose exec pipeline make all MES=2025-01
#
# Runs GNU make on the repository mounted at /workspace, with three adjustments for the container:
#   1. make -e: the container settings of docker-compose.yml (DATA_DIR=/data and the service names of
#      the Dagster Postgres, Superset and the Pushgateway) win over the host values that make reads
#      from .env. Everything else in .env is used as it is.
#   2. .env values that point to this computer are translated: an Airbyte API on localhost is reached
#      through host.docker.internal, and the Snowflake key is read from SNOWFLAKE_KEYS_DIR, which is
#      mounted at /keys. The key is used through a private copy (0600): Docker Desktop shows files
#      mounted from Windows as writable by everyone, and the Snowflake connector refuses such a key.
#   3. On Linux, make runs as the owner of the repository, so DATA_DIR and the repository never get
#      files owned by root. Docker Desktop (Windows, macOS) maps the owner by itself.
# The libraries come from requirements.txt, built into the image at /opt/venv. make never reinstalls
# them here (-o), and `docker compose up -d` rebuilds the image when requirements.txt changes.
set -eu

env_file=/workspace/.env
from_env_file() {  # last value of $1 in .env, without CR or surrounding quotes
    [ -f "$env_file" ] || return 0
    sed -n "s/^$1=//p" "$env_file" | tail -n 1 | tr -d '\r' | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"
}

airbyte_url=${AIRBYTE_API_URL:-$(from_env_file AIRBYTE_API_URL)}
if [ -n "$airbyte_url" ]; then
    AIRBYTE_API_URL=$(printf '%s' "$airbyte_url" | sed -E 's#^(https?://)(localhost|127\.0\.0\.1)([:/]|$)#\1host.docker.internal\3#')
    export AIRBYTE_API_URL
fi

owner_uid=$(stat -c %u /workspace)
owner_gid=$(stat -c %g /workspace)

key_path=${SNOWFLAKE_PRIVATE_KEY_PATH:-$(from_env_file SNOWFLAKE_PRIVATE_KEY_PATH)}
if [ -n "$key_path" ]; then
    key_name=$(printf '%s' "$key_path" | sed 's#.*[/\\]##')
    SNOWFLAKE_PRIVATE_KEY_PATH=/keys/$key_name
    private_dir=/tmp/snowflake-keys
    if [ -f "/keys/$key_name" ] && mkdir -p "$private_dir" && cp "/keys/$key_name" "$private_dir/$key_name" \
        && chmod 700 "$private_dir" && chmod 600 "$private_dir/$key_name"; then
        if [ "$(id -u)" = 0 ]; then chown -R "$owner_uid:$owner_gid" "$private_dir" || true; fi
        SNOWFLAKE_PRIVATE_KEY_PATH=$private_dir/$key_name
    fi
    export SNOWFLAKE_PRIVATE_KEY_PATH
fi

set -- -e -o "${VENV_DIR:-/opt/venv}/.installed" "$@"
if [ "$(id -u)" = 0 ] && [ "$owner_uid" != 0 ]; then
    exec setpriv --reuid="$owner_uid" --regid="$owner_gid" --clear-groups /usr/bin/make "$@"
fi
exec /usr/bin/make "$@"
