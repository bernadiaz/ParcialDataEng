# Imagen del worker del pipeline (Python 3.12 + DuckDB).
# Pensada para notebooks ~8 GB RAM: sin Jupyter ni Airbyte embebido.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY contracts ./contracts
COPY sql ./sql
COPY dbt_taxi ./dbt_taxi
COPY tests ./tests
COPY Makefile ./

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# Usuario no-root
RUN useradd --create-home --uid 1000 pipeline \
    && mkdir -p /app/data \
    && chown -R pipeline:pipeline /app
USER pipeline

ENTRYPOINT ["make"]
CMD ["help"]
