FROM apache/superset:5.0.0

USER root
# Database drivers: Snowflake (business dashboards on the marts) and DuckDB (offline validation copy).
COPY requirements-superset.txt /tmp/requirements-superset.txt
RUN . /app/.venv/bin/activate \
    && if command -v uv >/dev/null 2>&1; then uv pip install --no-cache -r /tmp/requirements-superset.txt; \
       else python -m pip install --no-cache-dir -r /tmp/requirements-superset.txt; fi
COPY --chown=superset:superset superset_config.py /app/pythonpath/superset_config.py
COPY --chown=superset:superset docker-init.sh /app/docker-init.sh
RUN chmod +x /app/docker-init.sh

USER superset
CMD ["/app/docker-init.sh"]
