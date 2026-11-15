# Dagster UI of docker compose (http://localhost:3003).
# `make all` runs the pipeline on the host and writes its run history to the dagster-postgres service;
# this UI reads the same history, read only. The image only holds the Python dependencies, taken from
# pyproject.toml (the same pins as the host's .venv). The code is the repository, mounted read only,
# so a code change needs no rebuild.
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml /tmp/pyproject.toml
# Runtime dependencies plus the dbt adapters of the dev extra (dbt-duckdb parses the project offline).
RUN python -c "import tomllib; p = tomllib.load(open('/tmp/pyproject.toml', 'rb'))['project']; print('\n'.join(p['dependencies'] + [d for d in p['optional-dependencies']['dev'] if d.startswith('dbt-')]))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && mkdir -p /opt/dagster/home /opt/dagster/data/warehouse /opt/dagster/dbt_target /opt/dagster/dbt_logs /opt/dagster/compute_logs

WORKDIR /opt/nyc_taxi
EXPOSE 3003
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=10 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3003/server_info', timeout=4)"
CMD ["sh", "/opt/nyc_taxi/dagster/entrypoint.sh"]
