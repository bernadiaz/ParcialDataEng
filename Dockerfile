# Pipeline image of docker compose (service "pipeline"): Python 3.12, GNU make, git, curl, openssl and
# every library of requirements.txt. Any computer that only has Docker (Windows, Linux or macOS) runs
# the whole pipeline with it, without installing make or Python:
#
#   docker compose up -d
#   docker compose exec pipeline make all MES=2025-01                                        # cloud
#   docker compose exec pipeline make all MES=2025-01 INGEST_MODE=direct WAREHOUSE=duckdb    # offline
#
# The repository is mounted at /workspace, so a code change needs no rebuild. The libraries live in
# /opt/venv, outside the repository: the .venv of the host is never touched. `make` in this image is
# docker/pipeline-make.sh, which adapts the .env of the host to the container.
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV_DIR=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HOME=/home/pipeline

# make runs the Makefile; git, curl and openssl help with the repository, the APIs and the Snowflake
# key pair; procps gives ps/top to watch a run. setpriv and stat come with the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends make git curl ca-certificates openssl procps \
    && rm -rf /var/lib/apt/lists/*

# Every library of the pipeline, at the versions it was validated with.
COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && touch /opt/venv/.installed \
    && mkdir -p /home/pipeline \
    && chmod 1777 /home/pipeline

# dbt artifacts of the container (DBT_TARGET_PATH and DBT_LOG_PATH in docker-compose.yml), writable by
# the user that runs make. A separate layer, so changing it never reinstalls the libraries.
RUN mkdir -p /opt/dbt/target /opt/dbt/logs && chmod 1777 /opt/dbt/target /opt/dbt/logs

COPY docker/pipeline-make.sh /usr/local/bin/make
# A Windows checkout without .gitattributes could add CR to the script: strip it so sh can run it.
RUN sed -i 's/\r$//' /usr/local/bin/make && chmod 755 /usr/local/bin/make \
    && command -v setpriv >/dev/null && /usr/bin/make --version | head -n 1

WORKDIR /workspace
# The container stays up; every run is `docker compose exec pipeline make ...`.
CMD ["sleep", "infinity"]
