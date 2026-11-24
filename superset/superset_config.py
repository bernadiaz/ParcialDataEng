"""Superset settings for the NYC Taxi dashboards (secrets come from the environment / .env)."""
import os
import warnings
from datetime import timedelta

JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=4)

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

# The offline validation copy is a local DuckDB file mounted read only.
PREVENT_UNSAFE_DB_CONNECTIONS = False

BABEL_DEFAULT_LOCALE = "en"
ROW_LIMIT = 50000
SQL_MAX_ROW = 100000
WTF_CSRF_ENABLED = True

# One gunicorn worker on one laptop: the rate limiter's in-memory storage is the right one. Naming it
# explicitly keeps Flask-Limiter from warning on every start that no storage was configured.
RATELIMIT_STORAGE_URI = "memory://"

# Superset's own dataset hooks (SqlaTable.load_database, called while the session flushes) make SQLAlchemy
# warn every time a dataset's SQL is updated, which `make all` does for each new month. Superset handles
# it; the notices are silenced by their exact text, so any other SQLAlchemy warning still shows up.
for _message in (
    r"Usage of the '(related attribute set|collection remove|collection append)' operation is not currently "
    r"supported within the execution stage of the flush process",
    r"Attribute history events accumulated on \d+ previously clean instances within inner-flush event handlers",
):
    warnings.filterwarnings("ignore", message=_message)
