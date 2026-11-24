"""Creates or updates the Superset business dashboards (English): assigned month vs the same month last year.

`make all` runs it as the last Dagster asset (`superset_dashboards`) whenever the docker compose stack
is up, so the dashboards follow every run without an extra command. Objects are matched by name and
updated, so it can run again safely (`make superset-dashboards` runs it alone). It creates:
  database   WAREHOUSE=snowflake -> the Snowflake marts through the service user's key pair
             WAREHOUSE=duckdb    -> an offline copy of the marts (<DATA_DIR>/bi/nyc_taxi_bi.duckdb)
  datasets   virtual SQL datasets on marts.fact_trips / agg_zone_hour / dim_zone / dim_date
  dashboards Executive Overview, Demand Patterns, Pickup Zones, Congestion Relief Zone,
             Payments & Tips, Airports, Data Quality & Quarantine

These follow the last command. The dashboards that back each report of results/ (one per month, kept for
every month) are built by src/respaldo.py, which this command also runs.

    python -m src.dashboards --mes 2025-01
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from src.config import Month, Settings, duckdb_config, get_logger, loopback

log = get_logger("superset")
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PERIOD_LABEL = re.compile(r"\b(?:" + "|".join(MONTH_ABBR) + r") \d{4}\b")  # "Feb 2025" in a chart name
ASSIGNED_COLOR, COMPARISON_COLOR = "#1A85A0", "#B2B2B2"
DEFAULT_URL = "http://localhost:8090"
SUPERSET_DUCKDB_MEMORY = "512MB"  # per query budget of the offline copy inside the Superset container


def superset_url() -> str:
    """SUPERSET_URL, or http://localhost:<SUPERSET_PORT> (the port docker compose publishes, 8090 by default)."""
    port = os.environ.get("SUPERSET_PORT", "").strip()
    return os.environ.get("SUPERSET_URL", "").strip() or (f"http://localhost:{port}" if port else DEFAULT_URL)


def superset_public_url() -> str:
    """Superset's address for a browser on this computer (the links of the reports). Inside the pipeline container
    SUPERSET_URL is the service name (http://superset:8088), which a browser cannot open."""
    url = superset_url()
    if urlparse(url).hostname == "superset":
        return f"http://localhost:{os.environ.get('SUPERSET_PORT', '').strip() or '8090'}"
    return url.rstrip("/")


def superset_expected() -> bool:
    """True when the docker compose stack publishes Superset (its port accepts connections).

    Docker publishes the port as soon as the container starts, even while Superset still runs its
    first-start migrations, so this answers at once. SupersetAPI then waits for /health."""
    parsed = urlparse(loopback(superset_url()))
    host, port = parsed.hostname or "127.0.0.1", parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        socket.create_connection((host, port), timeout=3).close()
        return True
    except OSError:
        return False


# --- Superset REST API -------------------------------------------------------------------------------------
class SupersetAPI:
    def __init__(self, url: str, user: str, password: str):
        self.http = httpx.Client(base_url=loopback(url).rstrip("/"), timeout=180)
        # The first `docker compose up -d` builds the image and runs the metadata migrations: wait for it.
        deadline = time.monotonic() + float(os.environ.get("SUPERSET_WAIT_SECONDS", "900"))
        while True:
            try:
                if self.http.get("/health").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Superset is not reachable at {url}: start the stack with `docker compose up -d`")
            time.sleep(5)
        token = self._ok(self.http.post("/api/v1/security/login", json={
            "username": user, "password": password, "provider": "db", "refresh": True}))["access_token"]
        self.http.headers["Authorization"] = f"Bearer {token}"
        csrf = self._ok(self.http.get("/api/v1/security/csrf_token/"))["result"]
        self.http.headers.update({"X-CSRFToken": csrf, "Referer": url})

    @staticmethod
    def _ok(response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise RuntimeError(f"Superset API {response.request.method} {response.request.url.path}: "
                               f"HTTP {response.status_code} {response.text[:500]}")
        return response.json() if response.content else {}

    def list_all(self, resource: str) -> list[dict[str, Any]]:
        """Every object of a resource (the API answers pages of 100)."""
        items: list[dict[str, Any]] = []
        while True:
            body = self._ok(self.http.get(f"/api/v1/{resource}/", params={"q": f"(page:{len(items) // 100},page_size:100)"}))
            items += body.get("result", [])
            if not body.get("result") or len(items) >= body.get("count", 0):
                return items

    def _index(self, resource: str, field: str) -> dict[Any, int]:
        """Value of the field -> id, read once per run: listing every chart again for each chart took minutes once
        there were more than a hundred of them."""
        indexes = self.__dict__.setdefault("_indexes", {})
        if (resource, field) not in indexes:
            found: dict[Any, int] = {}
            for item in self.list_all(resource):
                found.setdefault(item.get(field), item["id"])
            indexes[resource, field] = found
        return indexes[resource, field]

    def find(self, resource: str, field: str, value: str) -> int | None:
        return self._index(resource, field).get(value)

    def upsert(self, resource: str, field: str, payload: dict[str, Any], update: dict[str, Any] | None = None) -> int:
        existing = self.find(resource, field, payload[field])
        if existing is None:
            created = self._ok(self.http.post(f"/api/v1/{resource}/", json=payload))["id"]
            self._index(resource, field)[payload[field]] = created
            return created
        self._ok(self.http.put(f"/api/v1/{resource}/{existing}", json=update if update is not None else payload))
        return existing

    def dashboard_by_slug(self, slug: str) -> int | None:
        """GET /api/v1/dashboard/<slug> answers with the dashboard or 404."""
        response = self.http.get(f"/api/v1/dashboard/{slug}")
        if response.status_code == 404:
            return None
        return self._ok(response)["result"]["id"]

    def remove_stale_charts(self, dashboard_id: int, keep: set[int]) -> int:
        """Deletes the charts of this dashboard built for an earlier comparison.

        Chart names carry the period ("Trips Feb 2025"), so a run for another month creates its own
        charts and the old ones would stay attached to the dashboard, out of its layout. Only charts
        whose name has a period label are removed: a chart someone added by hand is left alone."""
        charts = self._ok(self.http.get(f"/api/v1/dashboard/{dashboard_id}/charts")).get("result", [])
        stale = [c["id"] for c in charts if c["id"] not in keep and PERIOD_LABEL.search(c.get("slice_name") or "")]
        names = self._index("chart", "slice_name")
        for chart_id in stale:
            self._ok(self.http.delete(f"/api/v1/chart/{chart_id}"))
            for name in [n for n, i in names.items() if i == chart_id]:
                del names[name]
        return len(stale)

    def refresh_dataset(self, dataset_id: int) -> None:
        self._ok(self.http.put(f"/api/v1/dataset/{dataset_id}/refresh"))

    def dataset_columns(self, dataset_id: int) -> dict[str, str]:
        """lower-case name -> name exactly as the database returns it (Snowflake: PERIOD, TRIPS...)."""
        columns = self._ok(self.http.get(f"/api/v1/dataset/{dataset_id}"))["result"]["columns"]
        return {c["column_name"].lower(): c["column_name"] for c in columns}


def match_columns(params: dict[str, Any], columns: dict[str, str]) -> dict[str, Any]:
    """Points every column reference of a chart at the dataset's real column name.

    Snowflake returns unquoted aliases in upper case (period -> PERIOD), while DuckDB keeps them in
    lower case, and Superset looks columns up by exact name. SQL expressions (metrics, WHERE
    filters) are left alone, because unquoted identifiers are case-insensitive in both engines."""
    def real(name: Any) -> Any:
        return columns.get(name.lower(), name) if isinstance(name, str) else name

    out = dict(params)
    if "x_axis" in out:
        out["x_axis"] = real(out["x_axis"])
    if isinstance(out.get("groupby"), list):
        out["groupby"] = [real(c) for c in out["groupby"]]
    elif isinstance(out.get("groupby"), str):
        out["groupby"] = real(out["groupby"])
    if out.get("all_columns"):
        out["all_columns"] = [real(c) for c in out["all_columns"]]
    if out.get("order_by_cols"):
        out["order_by_cols"] = [json.dumps([real(json.loads(o)[0]), json.loads(o)[1]]) for o in out["order_by_cols"]]
    if out.get("column_config"):
        out["column_config"] = {real(k): v for k, v in out["column_config"].items()}
    return out


# --- connection -------------------------------------------------------------------------------------------------
# Lineage/audit text columns that no dashboard reads: left out of the BI copy to keep it small.
BI_EXCLUDED_COLUMNS = {"fact_trips": ("trip_key", "source_file", "quality_flags"), "yellow_quarantine": ("run_id",)}
BI_RAW_TABLES = ("yellow_quarantine",)


def export_bi_copy(settings: Settings, month: Month | None = None) -> Path:
    """Offline mode: marts copied to a DuckDB file in v1.3 storage format (Superset 5 ships DuckDB 1.3).

    The dashboards compare MES with the same month of the previous year, so the tables partitioned by
    (year, month) only bring those two months: the warehouse keeps every month ever processed, and the
    copy stays small however many months it holds. Without a month every row is copied.

    DuckDB 2.0 compresses text with DICT_FSST even in v1.3 files, and DuckDB 1.3 reads those columns
    back as NULL (zone names vanish and the airport filter matches nothing). The export disables that
    method, so text is stored in a format DuckDB 1.3 reads."""
    import duckdb

    target = settings.data_dir / "bi" / "nyc_taxi_bi.duckdb"
    tmp = target.with_suffix(".tmp.duckdb")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(config=duckdb_config())
    con.execute("SET disabled_compression_methods = 'dict_fsst'")
    con.execute(f"ATTACH '{settings.warehouse_db.as_posix()}' AS wh (READ_ONLY)")
    con.execute(f"ATTACH '{tmp.as_posix()}' AS bi (STORAGE_VERSION 'v1.3.0')")
    # Every mart, plus the quarantine table (the Data Quality & Quarantine dashboard shows its rows).
    tables = con.execute(
        "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = 'wh' "
        "AND (schema_name = 'marts' OR (schema_name = 'raw' AND list_contains(?, table_name)))", [list(BI_RAW_TABLES)]).fetchall()
    for schema in sorted({s for s, _ in tables}):
        con.execute(f"CREATE SCHEMA bi.{schema}")
    for schema, name in tables:
        existing = {c for (c,) in con.execute(
            "SELECT column_name FROM duckdb_columns() WHERE database_name = 'wh' AND schema_name = ? "
            "AND table_name = ?", [schema, name]).fetchall()}
        excluded = [c for c in BI_EXCLUDED_COLUMNS.get(name, ()) if c in existing]
        select = f"* EXCLUDE ({', '.join(excluded)})" if excluded else "*"
        scope = (f" WHERE month = {month.month} AND year IN ({month.year}, {month.comparison.year})"
                 if month is not None and {"year", "month"} <= existing else "")
        con.execute(f"CREATE TABLE bi.{schema}.{name} AS SELECT {select} FROM wh.{schema}.{name}{scope}")
    con.execute("DETACH bi")
    con.close()
    os.replace(tmp, target)
    log.info("offline BI copy: %s (%d tables%s)", target, len(tables), f", {month} and {month.comparison}" if month else "")
    return target


def database_payload(settings: Settings, month: Month | None = None, export: bool = True) -> tuple[dict[str, Any], str]:
    """Superset connection of this warehouse. export=False reuses the offline BI copy that this run already wrote."""
    if settings.warehouse == "duckdb":
        if export or not (settings.data_dir / "bi" / "nyc_taxi_bi.duckdb").exists():
            export_bi_copy(settings, month)
        return {
            "database_name": "NYC Taxi (DuckDB offline copy)",
            "sqlalchemy_uri": "duckdb:////app/data/bi/nyc_taxi_bi.duckdb",
            "expose_in_sqllab": True,
            # DuckDB inside Superset would take 80% of the Docker VM's RAM by default; the container
            # has a 1.5 GiB limit (docker-compose.yml), so its queries get a fixed budget.
            "extra": json.dumps({"engine_params": {"connect_args": {
                "read_only": True, "config": {"memory_limit": SUPERSET_DUCKDB_MEMORY, "threads": "2"}}}}),
        }, "marts"
    env = os.environ
    key_file = env.get("SUPERSET_SNOWFLAKE_KEY_FILE", "").strip()
    if not key_file:
        raise RuntimeError("Superset needs the service user's key pair: set SUPERSET_SNOWFLAKE_KEY_FILE and SNOWFLAKE_KEYS_DIR in .env")
    connect_args = {"authenticator": "SNOWFLAKE_JWT", "private_key_file": f"/app/keys/{key_file}"}
    if env.get("SUPERSET_SNOWFLAKE_KEY_PASSPHRASE", "").strip():
        connect_args["private_key_file_pwd"] = env["SUPERSET_SNOWFLAKE_KEY_PASSPHRASE"].strip()
    uri = (f"snowflake://{env.get('SUPERSET_SNOWFLAKE_USER', 'TAXI_SVC')}@{env['SNOWFLAKE_ACCOUNT']}/"
           f"{env.get('SNOWFLAKE_DATABASE', 'NYC_TAXI')}/MARTS?role={env.get('SNOWFLAKE_ROLE', 'TAXI_PIPELINE')}"
           f"&warehouse={env.get('SUPERSET_SNOWFLAKE_WAREHOUSE', 'WH_TAXI_DEV')}")
    return {
        "database_name": "NYC Taxi (Snowflake)",
        "sqlalchemy_uri": uri,
        "expose_in_sqllab": True,
        "extra": json.dumps({"engine_params": {"connect_args": connect_args}}),
    }, "MARTS"


# --- datasets (portable SQL: runs on Snowflake and DuckDB) -----------------------------------------------------------
def datasets(month: Month) -> dict[str, str]:
    y, m, cy = month.year, month.month, month.comparison.year
    a, b = f"{MONTH_ABBR[m - 1]} {y}", f"{MONTH_ABBR[m - 1]} {cy}"
    period = f"case when {{alias}}year = {y} then '{a}' else '{b}' end"
    scope = f"{{alias}}month = {m} and {{alias}}year in ({y}, {cy})"
    p = lambda alias="": period.format(alias=alias)  # noqa: E731
    s = lambda alias="": scope.format(alias=alias)  # noqa: E731
    return {
        "nyc_monthly_kpis": f"""
select {p()} as period,
       count(*) as trips,
       sum(total_amount) as revenue,
       avg(fare_amount) as avg_fare,
       avg(total_amount) as avg_total_amount,
       avg(trip_distance) as avg_distance_mi,
       avg(duration_min) as avg_duration_min,
       avg(case when payment_type = 1 then tip_pct end) as avg_card_tip_pct,
       100.0 * sum(case when cbd_congestion_fee > 0 then 1 else 0 end) / count(*) as pct_trips_with_cbd_fee,
       100.0 * sum(case when payment_type = 0 then 1 else 0 end) / count(*) as pct_flex_fare,
       100.0 * sum(case when payment_type = 2 then 1 else 0 end) / count(*) as pct_cash
from marts.fact_trips
where {s()}
group by 1""",
        # Aggregated per day first (62 rows), then joined to dim_date: the join never sees trip rows.
        "nyc_daily": f"""
with by_day as (
    select year, pickup_date,
           count(*) as trips,
           sum(total_amount) as revenue,
           avg(fare_amount) as avg_fare,
           100.0 * sum(case when cbd_congestion_fee > 0 then 1 else 0 end) / count(*) as pct_with_cbd_fee
    from marts.fact_trips
    where {s()}
    group by year, pickup_date
)
select {p('b.')} as period, d.day_of_month, d.day_name, b.pickup_date, b.trips, b.revenue, b.avg_fare, b.pct_with_cbd_fee
from by_day as b
join marts.dim_date as d on d.date_key = b.pickup_date""",
        "nyc_hourly": f"""
select {p()} as period, pickup_hour,
       sum(trips) as trips,
       sum(total_revenue) as revenue,
       sum(avg_duration_min * trips) as duration_x_trips
from marts.agg_zone_hour
where {s()}
group by 1, 2""",
        "nyc_weekday_hour": f"""
with by_date_hour as (
    select year, pickup_date, pickup_hour, sum(trips) as trips
    from marts.agg_zone_hour
    where {s()}
    group by year, pickup_date, pickup_hour
)
select {p('b.')} as period,
       concat(cast(d.day_of_week_iso as varchar), ' ', d.day_name) as weekday,
       b.pickup_hour,
       sum(b.trips) as trips
from by_date_hour as b
join marts.dim_date as d on d.date_key = b.pickup_date
group by 1, 2, 3""",
        "nyc_borough": f"""
with by_zone as (
    select year, pu_location_id, sum(trips) as trips, sum(total_revenue) as revenue
    from marts.agg_zone_hour
    where {s()}
    group by year, pu_location_id
)
select {p('b.')} as period, coalesce(z.borough, 'Unknown') as borough,
       sum(b.trips) as trips, sum(b.revenue) as revenue
from by_zone as b
join marts.dim_zone as z on z.location_id = b.pu_location_id
group by 1, 2""",
        "nyc_top_zones": f"""
with by_zone as (
    select year, pu_location_id, sum(trips) as trips, sum(total_revenue) as revenue
    from marts.agg_zone_hour
    where {s()}
    group by year, pu_location_id
),
top_zones as (
    select pu_location_id from by_zone where year = {y} order by trips desc limit 15
)
select {p('b.')} as period, z.zone, z.borough, b.trips, b.revenue
from by_zone as b
join top_zones as t on t.pu_location_id = b.pu_location_id
join marts.dim_zone as z on z.location_id = b.pu_location_id""",
        "nyc_zone_change": f"""
with by_zone as (
    select pu_location_id,
           sum(case when year = {y} then trips else 0 end) as trips_assigned,
           sum(case when year = {cy} then trips else 0 end) as trips_comparison
    from marts.agg_zone_hour
    where {s()}
    group by pu_location_id
)
select z.zone, z.borough, b.trips_assigned, b.trips_comparison,
       b.trips_assigned - b.trips_comparison as trips_change,
       round(100.0 * (b.trips_assigned - b.trips_comparison) / nullif(b.trips_comparison, 0), 2) as trips_change_pct
from by_zone as b
join marts.dim_zone as z on z.location_id = b.pu_location_id
where b.trips_assigned + b.trips_comparison >= 1000""",
        "nyc_payments": f"""
select {p()} as period,
       case payment_type when 0 then 'Flex Fare' when 1 then 'Credit card' when 2 then 'Cash'
            when 3 then 'No charge' when 4 then 'Dispute' when 5 then 'Unknown' when 6 then 'Voided trip' end as payment_type,
       count(*) as trips,
       avg(case when fare_amount > 0 then tip_pct end) as avg_tip_pct,
       100.0 * sum(case when fare_amount > 0 then tip_amount else 0 end)
             / nullif(sum(case when fare_amount > 0 then fare_amount else 0 end), 0) as weighted_tip_pct,
       avg(total_amount) as avg_total_amount
from marts.fact_trips
where {s()}
group by 1, 2""",
        # One pass over the trips: each one is joined to the 2 airport ids (not to the 265 zones) at
        # both ends, aggregated by origin and destination airport, and only then split by direction.
        "nyc_airports": f"""
with airports as (
    select location_id, zone from marts.dim_zone where zone in ('JFK Airport', 'LaGuardia Airport')
),
by_airport as (
    select f.year, pa.zone as pu_airport, da.zone as do_airport,
           count(*) as trips, sum(f.fare_amount) as fare_sum, sum(f.total_amount) as total_sum,
           sum(f.duration_min) as duration_sum, sum(f.trip_distance) as distance_sum
    from marts.fact_trips as f
    left join airports as pa on pa.location_id = f.pu_location_id
    left join airports as da on da.location_id = f.do_location_id
    where {s('f.')} and (pa.location_id is not null or da.location_id is not null)
    group by f.year, pa.zone, da.zone
)
select {p()} as period, pu_airport as airport, 'Pickup at the airport' as direction,
       sum(trips) as trips, sum(fare_sum) as fare_sum, sum(total_sum) as total_sum,
       sum(duration_sum) as duration_sum, sum(distance_sum) as distance_sum
from by_airport where pu_airport is not null
group by 1, 2, 3
union all
select {p()} as period, do_airport as airport, 'Dropoff at the airport' as direction,
       sum(trips) as trips, sum(fare_sum) as fare_sum, sum(total_sum) as total_sum,
       sum(duration_sum) as duration_sum, sum(distance_sum) as distance_sum
from by_airport where do_airport is not null
group by 1, 2, 3""",
        "nyc_cbd_zones": f"""
with by_zone as (
    select pu_location_id, count(*) as trips,
           sum(case when cbd_congestion_fee > 0 then 1 else 0 end) as trips_with_fee
    from marts.fact_trips
    where year = {y} and month = {m}
    group by pu_location_id
    having count(*) >= 1000
)
select z.zone, z.borough, b.trips, 100.0 * b.trips_with_fee / b.trips as pct_with_cbd_fee
from by_zone as b
join marts.dim_zone as z on z.location_id = b.pu_location_id""",
        # Quality gate: every row read is accepted (fact_trips) or quarantined (raw.yellow_quarantine).
        "nyc_quality_totals": f"""
with accepted as (
    select year, month, count(*) as accepted_rows from marts.fact_trips where {s()} group by 1, 2
), quarantined as (
    select year, month, count(*) as quarantined_rows from raw.yellow_quarantine where {s()} group by 1, 2
)
select {p('a.')} as period,
       a.accepted_rows + coalesce(q.quarantined_rows, 0) as rows_read,
       a.accepted_rows,
       coalesce(q.quarantined_rows, 0) as quarantined_rows,
       100.0 * coalesce(q.quarantined_rows, 0) / (a.accepted_rows + coalesce(q.quarantined_rows, 0)) as pct_quarantined
from accepted as a
left join quarantined as q on q.year = a.year and q.month = a.month""",
        "nyc_quarantine_rules": f"""
select {p()} as period, rule_id, quarantined_rows
from marts.agg_quarantine_rule
where {s()}""",
        "nyc_quarantine_rows": f"""
select {p()} as period, violated_rules, source_file, source_row_number,
       tpep_pickup_datetime as pickup_at, tpep_dropoff_datetime as dropoff_at, trip_distance,
       fare_amount, total_amount, passenger_count, pu_location_id, do_location_id
from raw.yellow_quarantine
where {s()}""",
    }


# --- chart helpers --------------------------------------------------------------------------------------------------
def metric(sql: str, label: str) -> dict[str, Any]:
    return {"expressionType": "SQL", "sqlExpression": sql, "label": label}


def where(sql: str) -> dict[str, Any]:
    return {"expressionType": "SQL", "sqlExpression": sql, "clause": "WHERE"}


def big_number(m: dict, period: str, subheader: str, fmt: str = "SMART_NUMBER") -> dict[str, Any]:
    return {"viz_type": "big_number_total", "metric": m, "adhoc_filters": [where(f"period = '{period}'")],
            "subheader": subheader, "y_axis_format": fmt, "header_font_size": 0.4, "subheader_font_size": 0.15}


def series(kind: str, x: str, metrics: list[dict], x_title: str, y_title: str, y_fmt: str = "SMART_NUMBER",
           filters: list[dict] | None = None, sort_by_metric: bool = False, horizontal: bool = False) -> dict[str, Any]:
    params = {
        "viz_type": f"echarts_timeseries_{kind}", "x_axis": x, "metrics": metrics, "groupby": ["period"],
        "adhoc_filters": filters or [], "row_limit": 10000, "truncate_metric": True, "show_legend": True,
        "legendType": "scroll", "legendOrientation": "top", "rich_tooltip": True, "tooltipTimeFormat": "smart_date",
        "x_axis_title": x_title, "x_axis_title_margin": 30, "y_axis_title": y_title, "y_axis_title_margin": 50,
        "y_axis_title_position": "Left", "y_axis_format": y_fmt, "xAxisForceCategorical": True,
        "color_scheme": "supersetColors", "markerEnabled": kind == "line", "x_axis_sort_asc": not sort_by_metric,
    }
    if sort_by_metric:
        params["x_axis_sort"] = metrics[0]["label"]
    if horizontal:
        params["orientation"] = "horizontal"
    return params


def table(columns: list[str], formats: dict[str, str] | None = None, order: str | None = None) -> dict[str, Any]:
    return {"viz_type": "table", "query_mode": "raw", "all_columns": columns,
            "order_by_cols": [json.dumps([order, False])] if order else [], "row_limit": 1000,
            "server_page_length": 25, "show_cell_bars": True, "include_search": False, "table_timestamp_format": "smart_date",
            "column_config": {c: {"d3NumberFormat": f} for c, f in (formats or {}).items()}}


def heatmap(period: str) -> dict[str, Any]:
    return {"viz_type": "heatmap_v2", "x_axis": "pickup_hour", "groupby": "weekday", "metric": metric("SUM(trips)", "Trips"),
            "adhoc_filters": [where(f"period = '{period}'")], "row_limit": 10000, "sort_x_axis": "alpha_asc",
            "sort_y_axis": "alpha_asc", "normalize_across": "heatmap", "linear_color_scheme": "blue_white_yellow",
            "show_legend": True, "show_percentage": False, "value_bounds": [None, None], "y_axis_format": "SMART_NUMBER",
            "xscale_interval": -1, "yscale_interval": -1, "left_margin": "auto", "bottom_margin": "auto"}


def dashboards(month: Month) -> list[dict[str, Any]]:
    a = f"{MONTH_ABBR[month.month - 1]} {month.year}"
    b = f"{MONTH_ABBR[month.month - 1]} {month.comparison.year}"
    trips, revenue = metric("SUM(trips)", "Trips"), metric("SUM(revenue)", "Revenue (USD)")
    rows: list[dict[str, Any]] = [
        {
            "title": f"NYC Taxi | Executive Overview: {a} vs {b}", "slug": "nyc-taxi-overview",
            "layout": [
                [("md", f"### Yellow taxi trips, {a} vs {b}\nAccepted trips only (rows that passed the quality gate). "
                        "Revenue = total charged to passengers (`total_amount`, cash tips excluded).", 12, 14)],
                [("Trips " + a, "nyc_monthly_kpis", big_number(metric("SUM(trips)", "Trips"), a, "Trips"), 2, 30),
                 ("Trips " + b, "nyc_monthly_kpis", big_number(metric("SUM(trips)", "Trips"), b, "Trips"), 2, 30),
                 ("Revenue " + a, "nyc_monthly_kpis", big_number(metric("SUM(revenue)", "Revenue"), a, "USD", "$,.3s"), 2, 30),
                 ("Revenue " + b, "nyc_monthly_kpis", big_number(metric("SUM(revenue)", "Revenue"), b, "USD", "$,.3s"), 2, 30),
                 ("Average fare " + a, "nyc_monthly_kpis", big_number(metric("MAX(avg_fare)", "Avg fare"), a, "USD per trip", "$,.2f"), 2, 30),
                 ("Average fare " + b, "nyc_monthly_kpis", big_number(metric("MAX(avg_fare)", "Avg fare"), b, "USD per trip", "$,.2f"), 2, 30)],
                [("Daily trips by day of month", "nyc_daily",
                  series("line", "day_of_month", [trips], "Day of month", "Trips"), 6, 50),
                 ("Daily revenue by day of month", "nyc_daily",
                  series("line", "day_of_month", [revenue], "Day of month", "Revenue (USD)", "$,.3s"), 6, 50)],
                [("KPI comparison", "nyc_monthly_kpis",
                  table(["period", "trips", "revenue", "avg_fare", "avg_total_amount", "avg_distance_mi", "avg_duration_min",
                         "avg_card_tip_pct", "pct_trips_with_cbd_fee", "pct_flex_fare", "pct_cash"],
                        {"trips": ",d", "revenue": "$,.0f", "avg_fare": "$,.2f", "avg_total_amount": "$,.2f",
                         "avg_distance_mi": ",.2f", "avg_duration_min": ",.1f", "avg_card_tip_pct": ",.1f",
                         "pct_trips_with_cbd_fee": ",.1f", "pct_flex_fare": ",.1f", "pct_cash": ",.1f"}), 12, 22)],
            ],
        },
        {
            "title": f"NYC Taxi | Demand Patterns: {a} vs {b}", "slug": "nyc-taxi-demand",
            "layout": [
                [("Trips by hour of day", "nyc_hourly", series("bar", "pickup_hour", [trips], "Pickup hour", "Trips"), 6, 50),
                 ("Average revenue per trip by hour", "nyc_hourly",
                  series("line", "pickup_hour", [metric("SUM(revenue) / SUM(trips)", "Revenue per trip")],
                         "Pickup hour", "USD per trip", "$,.2f"), 6, 50)],
                [(f"Trips by weekday and hour - {a}", "nyc_weekday_hour", heatmap(a), 6, 55),
                 (f"Trips by weekday and hour - {b}", "nyc_weekday_hour", heatmap(b), 6, 55)],
                [("Trips by pickup borough", "nyc_borough", series("bar", "borough", [trips], "Borough", "Trips", sort_by_metric=True), 6, 50),
                 ("Average trip duration by hour (minutes)", "nyc_hourly",
                  series("line", "pickup_hour", [metric("SUM(duration_x_trips) / SUM(trips)", "Minutes")],
                         "Pickup hour", "Minutes", ",.1f"), 6, 50)],
            ],
        },
        {
            "title": f"NYC Taxi | Pickup Zones: {a} vs {b}", "slug": "nyc-taxi-zones",
            "layout": [
                [(f"Top 15 pickup zones of {a}: trips in both months", "nyc_top_zones",
                  series("bar", "zone", [trips], "Pickup zone", "Trips", sort_by_metric=True), 12, 60)],
                [("Trips change by zone (zones with 1,000+ trips)", "nyc_zone_change",
                  table(["zone", "borough", "trips_assigned", "trips_comparison", "trips_change", "trips_change_pct"],
                        {"trips_assigned": ",d", "trips_comparison": ",d", "trips_change": "+,d", "trips_change_pct": "+,.2f"},
                        order="trips_assigned"), 12, 60)],
            ],
        },
        {
            "title": f"NYC Taxi | Congestion Relief Zone (CBD fee): {a} vs {b}", "slug": "nyc-taxi-cbd",
            "layout": [
                [("md", cbd_markdown(month), 12, 14)],
                [("Share of trips with CBD fee - " + a, "nyc_monthly_kpis",
                  big_number(metric("MAX(pct_trips_with_cbd_fee)", "% trips"), a, "% of trips with fee > 0", ",.1f"), 4, 50),
                 ("Daily share of trips with CBD fee (%)", "nyc_daily",
                  series("line", "day_of_month", [metric("MAX(pct_with_cbd_fee)", "% trips with fee")],
                         "Day of month", "% of trips", ",.1f"), 8, 50)],
                [("Pickup zones with the highest share of CBD-fee trips - " + a, "nyc_cbd_zones",
                  {**series("bar", "zone", [metric("MAX(pct_with_cbd_fee)", "% trips with fee")], "Pickup zone", "% of trips",
                            ",.1f", sort_by_metric=True), "groupby": [], "row_limit": 15}, 12, 55)],
            ],
        },
        {
            "title": f"NYC Taxi | Payments & Tips: {a} vs {b}", "slug": "nyc-taxi-payments",
            "layout": [
                [("md", "### Reading tips by payment type\nThe TLC records **credit card tips only**: cash tips are not "
                        "in `tip_amount`, so the cash tip percentage (about 0%) is a recording artifact, not customer behavior. "
                        "Flex Fare trips (payment type 0) also miss passenger count and rate code.", 12, 16)],
                [("Trips by payment type", "nyc_payments", series("bar", "payment_type", [trips], "Payment type", "Trips", sort_by_metric=True), 6, 50),
                 ("Average tip as % of fare by payment type", "nyc_payments",
                  series("bar", "payment_type", [metric("MAX(avg_tip_pct)", "Avg tip %")], "Payment type", "% of fare", ",.1f",
                         sort_by_metric=True), 6, 50)],
                [("Payments detail", "nyc_payments",
                  table(["period", "payment_type", "trips", "avg_tip_pct", "weighted_tip_pct", "avg_total_amount"],
                        {"trips": ",d", "avg_tip_pct": ",.2f", "weighted_tip_pct": ",.2f", "avg_total_amount": "$,.2f"},
                        order="trips"), 12, 30)],
            ],
        },
        {
            "title": f"NYC Taxi | Airports (JFK & LaGuardia): {a} vs {b}", "slug": "nyc-taxi-airports",
            "layout": [
                [("Pickups at the airport", "nyc_airports",
                  series("bar", "airport", [trips], "Airport", "Trips", filters=[where("direction = 'Pickup at the airport'")]), 6, 50),
                 ("Dropoffs at the airport", "nyc_airports",
                  series("bar", "airport", [trips], "Airport", "Trips", filters=[where("direction = 'Dropoff at the airport'")]), 6, 50)],
                [("Average fare of airport trips", "nyc_airports",
                  series("bar", "airport", [metric("SUM(fare_sum) / SUM(trips)", "Avg fare")], "Airport", "USD per trip", "$,.2f"), 6, 50),
                 ("Average duration of airport trips (minutes)", "nyc_airports",
                  series("bar", "airport", [metric("SUM(duration_sum) / SUM(trips)", "Minutes")], "Airport", "Minutes", ",.1f"), 6, 50)],
            ],
        },
        {
            "title": f"NYC Taxi | Data Quality & Quarantine: {a} vs {b}", "slug": "nyc-taxi-quality",
            "layout": [
                [("md", "### Quality gate and quarantine\nEvery row read ends in the curated layer (accepted) or in "
                        "quarantine (rejected), and the pipeline fails if `rows read = accepted + quarantined` does not "
                        "hold. Quarantined rows keep their original values, the source file and row number, and the reject "
                        "rules they violated (`RAW.YELLOW_QUARANTINE`). Warnings never drop a row.\n\n"
                        + rules_markdown(), 12, 46)],
                [("Quarantined rows " + a, "nyc_quality_totals",
                  big_number(metric("SUM(quarantined_rows)", "Quarantined"), a, "rows rejected by the quality gate"), 3, 30),
                 ("Quarantined rows " + b, "nyc_quality_totals",
                  big_number(metric("SUM(quarantined_rows)", "Quarantined"), b, "rows rejected by the quality gate"), 3, 30),
                 ("Quarantine share " + a, "nyc_quality_totals",
                  big_number(metric("MAX(pct_quarantined)", "% quarantined"), a, "% of rows read", ",.2f"), 3, 30),
                 ("Quarantine share " + b, "nyc_quality_totals",
                  big_number(metric("MAX(pct_quarantined)", "% quarantined"), b, "% of rows read", ",.2f"), 3, 30)],
                [("Reconciliation: rows read = accepted + quarantined", "nyc_quality_totals",
                  table(["period", "rows_read", "accepted_rows", "quarantined_rows", "pct_quarantined"],
                        {"rows_read": ",d", "accepted_rows": ",d", "quarantined_rows": ",d", "pct_quarantined": ",.2f"}), 5, 40),
                 ("Quarantined rows by violated rule", "nyc_quarantine_rules",
                  series("bar", "rule_id", [metric("SUM(quarantined_rows)", "Quarantined rows")], "Reject rule",
                         "Rows (a row can violate several rules)"), 7, 40)],
                [("Quarantined rows: original values and violated rules", "nyc_quarantine_rows",
                  table(["period", "violated_rules", "source_file", "source_row_number", "pickup_at", "dropoff_at",
                         "trip_distance", "fare_amount", "total_amount", "passenger_count", "pu_location_id",
                         "do_location_id"],
                        {"trip_distance": ",.2f", "fare_amount": "$,.2f", "total_amount": "$,.2f"}), 12, 70)],
            ],
        },
    ]
    return rows


def cbd_markdown(month: Month) -> str:
    """Header of the CBD dashboard, written for the two months being compared."""
    from datetime import datetime

    from src.calidad import load_rules

    params, _ = load_rules()
    start = datetime.fromisoformat(str(params.get("cbd_fee_start", "2025-01-05 00:00:00"))).date()

    def label(m: Month) -> str:
        return f"{MONTH_ABBR[m.month - 1]} {m.year}"

    lines = [f"### MTA Congestion Relief Zone toll\nThe per-trip `cbd_congestion_fee` starts on "
             f"**{MONTH_ABBR[start.month - 1]} {start.day}, {start.year}**."]
    for m in (month, month.comparison):
        if (m.year, m.month) < (start.year, start.month):
            lines.append(f"In {label(m)} the toll did not exist yet: the column is NULL (not 0) in the warehouse.")
        elif (m.year, m.month) == (start.year, start.month):
            lines.append(f"{label(m)} has the toll from day {start.day} on, so its monthly share is diluted by the first days.")
    if (month.comparison.year, month.comparison.month) >= (start.year, start.month):
        lines.append("Both months have the toll, so their shares can be compared directly.")
    return " ".join(lines)


def rules_markdown() -> str:
    """Rule table for the dashboard, read from contracts/quality_rules.yaml (the single source)."""
    from src.calidad import load_rules

    _, rules = load_rules()
    lines = ["| Rule | Severity | Description | Threshold |", "|---|---|---|---|"]
    for rule in rules:
        lines.append(f"| {rule.id} | {rule.severity} | {rule.description} | {rule.threshold.replace('|', '/')} |")
    return "\n".join(lines)


def position(layout: list[list[tuple]], chart_ids: dict[str, int], title: str) -> dict[str, Any]:
    pos: dict[str, Any] = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}},
    }
    for r, row in enumerate(layout):
        row_id = f"ROW-{r}"
        pos["GRID_ID"]["children"].append(row_id)
        pos[row_id] = {"type": "ROW", "id": row_id, "children": [], "parents": ["ROOT_ID", "GRID_ID"],
                       "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        for c, (name, dataset, *_rest) in enumerate(row):
            width, height = row[c][-2], row[c][-1]
            if name == "md":
                item_id = f"MARKDOWN-{r}-{c}"
                pos[item_id] = {"type": "MARKDOWN", "id": item_id, "children": [], "parents": ["ROOT_ID", "GRID_ID", row_id],
                                "meta": {"width": width, "height": height, "code": dataset}}
            else:
                item_id = f"CHART-{r}-{c}"
                pos[item_id] = {"type": "CHART", "id": item_id, "children": [], "parents": ["ROOT_ID", "GRID_ID", row_id],
                                "meta": {"chartId": chart_ids[name], "width": width, "height": height, "sliceName": name}}
            pos[row_id]["children"].append(item_id)
    return pos


def build(settings: Settings, month: Month) -> dict[str, Any]:
    """Creates or updates the connection, datasets and dashboards. Returns a summary for Dagster."""
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("SUPERSET_ADMIN_PASSWORD is empty: set it in .env (the same value docker compose uses)")
    url = superset_url()
    api = SupersetAPI(url, os.environ.get("SUPERSET_ADMIN_USER", "admin").strip() or "admin", password)

    db_payload, schema = database_payload(settings, month)
    db_id = api.upsert("database", "database_name", db_payload)
    log.info("database %s -> id %s", db_payload["database_name"], db_id)

    dataset_ids: dict[str, int] = {}
    dataset_columns: dict[str, dict[str, str]] = {}
    for name, sql in datasets(month).items():
        dataset_ids[name] = api.upsert("dataset", "table_name",
                                       {"database": db_id, "schema": schema, "table_name": name, "sql": sql.strip()},
                                       update={"sql": sql.strip(), "database_id": db_id, "schema": schema})
        api.refresh_dataset(dataset_ids[name])
        dataset_columns[name] = api.dataset_columns(dataset_ids[name])
    log.info("datasets: %s", ", ".join(dataset_ids))

    a = f"{MONTH_ABBR[month.month - 1]} {month.year}"
    b = f"{MONTH_ABBR[month.month - 1]} {month.comparison.year}"
    built: list[dict[str, Any]] = []
    for spec in dashboards(month):
        # Matched by slug, which never changes: the title carries the months ("... Feb 2025 vs Feb 2024"),
        # so matching by title would try to create a second dashboard with the same slug (HTTP 422).
        dash_id = api.dashboard_by_slug(spec["slug"])
        if dash_id is None:
            dash_id = api._ok(api.http.post("/api/v1/dashboard/", json={
                "dashboard_title": spec["title"], "slug": spec["slug"], "published": True}))["id"]
        else:
            api._ok(api.http.put(f"/api/v1/dashboard/{dash_id}", json={"dashboard_title": spec["title"], "published": True}))
        chart_ids: dict[str, int] = {}
        for row in spec["layout"]:
            for name, dataset, *rest in row:
                if name == "md":
                    continue
                params = match_columns(rest[0], dataset_columns[dataset]) | {"datasource": f"{dataset_ids[dataset]}__table"}
                payload = {"slice_name": name, "viz_type": params["viz_type"], "datasource_id": dataset_ids[dataset],
                           "datasource_type": "table", "params": json.dumps(params), "dashboards": [dash_id]}
                # Superset saves a chart's query (query_context) the first time it is opened in Explore,
                # with the column names of that moment. After a warehouse switch (period vs PERIOD) that
                # saved query would fail, so it is cleared and Superset rebuilds it from params.
                chart_ids[name] = api.upsert("chart", "slice_name", payload, update=payload | {"query_context": None})
        metadata = {"color_scheme": "supersetColors", "label_colors": {a: ASSIGNED_COLOR, b: COMPARISON_COLOR},
                    "refresh_frequency": 0, "timed_refresh_immune_slices": [], "expanded_slices": {},
                    "native_filter_configuration": [], "cross_filters_enabled": False}
        api._ok(api.http.put(f"/api/v1/dashboard/{dash_id}", json={
            "position_json": json.dumps(position(spec["layout"], chart_ids, spec["title"])),
            "json_metadata": json.dumps(metadata), "published": True}))
        removed = api.remove_stale_charts(dash_id, set(chart_ids.values()))
        log.info("dashboard %s -> /superset/dashboard/%s/ (%d charts%s)", spec["title"], spec["slug"], len(chart_ids),
                 f", {removed} charts of an earlier comparison removed" if removed else "")
        built.append({"title": spec["title"], "url": f"{url.rstrip('/')}/superset/dashboard/{spec['slug']}/",
                      "charts": len(chart_ids)})
    return {"database": db_payload["database_name"], "datasets": len(dataset_ids), "dashboards": built}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", required=True)
    args = parser.parse_args(argv)
    settings, month = Settings.from_env(), Month.parse(args.mes)
    build(settings, month)
    # The evidence dashboards of the reports, on the BI copy that build() has just refreshed, and their verification.
    from src import respaldo

    summary = respaldo.build(settings, month, exportar=False)
    print(f"Evidence dashboards: {summary['verificacion']}")
    for difference in summary["diferencias"]:
        print(f"DIFFERENCE  {difference}", file=sys.stderr)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
