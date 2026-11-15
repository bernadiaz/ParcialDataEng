"""Superset settings for the NYC Taxi dashboards (secrets come from the environment / .env)."""
import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

# The offline validation copy is a local DuckDB file mounted read only.
PREVENT_UNSAFE_DB_CONNECTIONS = False

BABEL_DEFAULT_LOCALE = "en"
ROW_LIMIT = 50000
SQL_MAX_ROW = 100000
WTF_CSRF_ENABLED = True
