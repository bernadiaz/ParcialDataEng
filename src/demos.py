"""Oral defense helpers (plan 5.7).

    python -m src.demos counts --label before            # snapshot of every layer, per month
    python -m src.demos counts --label after --compare before
    python -m src.demos show-quarantine --mes 2025-01    # one quarantined row per violated rule
    python -m src.demos quality-report --mes 2025-01     # prints the quality report
    python -m src.demos finops                           # Snowflake credits and time by query tag
"""
from __future__ import annotations

import argparse
import io
import itertools
import json
import sys
from pathlib import Path
from typing import Any

import duckdb

from src.config import ROOT, Month, Settings, duckdb_config, get_logger

log = get_logger("demos")


def _parquet_counts(con: duckdb.DuckDBPyConnection, base: Path, layer: str) -> dict[str, int]:
    if not any(base.rglob("*.parquet")):
        return {}
    rows = con.execute(
        f"SELECT year, month, count(*) FROM read_parquet('{base.as_posix()}/**/*.parquet', hive_partitioning = true) "
        "GROUP BY ALL ORDER BY ALL"
    ).fetchall()
    return {f"{layer} {int(y):04d}-{int(m):02d}": n for y, m, n in rows}


def _warehouse_counts(settings: Settings) -> dict[str, int]:
    queries = {
        "warehouse raw.yellow_trips": "SELECT year, month, count(*) FROM raw.yellow_trips GROUP BY 1, 2 ORDER BY 1, 2",
        "warehouse marts.fact_trips": "SELECT year, month, count(*) FROM marts.fact_trips GROUP BY 1, 2 ORDER BY 1, 2",
        "warehouse marts.agg_zone_hour (sum trips)": "SELECT year, month, sum(trips) FROM marts.agg_zone_hour GROUP BY 1, 2 ORDER BY 1, 2",
    }
    counts: dict[str, int] = {}
    if settings.warehouse == "duckdb":
        if not settings.warehouse_db.exists():
            return counts
        con = duckdb.connect(str(settings.warehouse_db), read_only=True, config=duckdb_config(in_memory=False))
        run = lambda sql: con.execute(sql).fetchall()  # noqa: E731
    else:
        from src.load_snowflake import snowflake_connect

        con = snowflake_connect(step="demo")

        def run(sql: str) -> list[tuple]:
            with con.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()
    try:
        for label, sql in queries.items():
            try:
                for y, m, n in run(sql):
                    counts[f"{label} {int(y):04d}-{int(m):02d}"] = int(n)
            except Exception as exc:  # table not built yet
                log.warning("%s: %s", label, str(exc).splitlines()[0])
    finally:
        con.close()
    return counts


def counts(settings: Settings, label: str, compare: str | None) -> int:
    con = duckdb.connect(config=duckdb_config())
    snapshot: dict[str, Any] = {}
    snapshot |= _parquet_counts(con, settings.curated_dir / "yellow", "curated")
    snapshot |= _parquet_counts(con, settings.quarantine_dir / "yellow", "quarantine")
    snapshot |= _warehouse_counts(settings)
    out_dir = settings.reports_dir / "counts"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"counts_{label}.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    previous = {}
    if compare:
        path = out_dir / f"counts_{compare}.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    width = max((len(k) for k in snapshot), default=20)
    print(f"\n{'layer / partition':<{width}}  {compare or '':>12}  {label:>12}  status")
    changed = 0
    for key in sorted(set(snapshot) | set(previous)):
        before, after = previous.get(key), snapshot.get(key)
        status = "" if not compare else ("unchanged" if before == after else "CHANGED")
        changed += status == "CHANGED"
        print(f"{key:<{width}}  {'' if before is None else f'{before:,}':>12}  {'' if after is None else f'{after:,}':>12}  {status}")
    if compare:
        print(f"\n{'All counts unchanged: the rerun is idempotent.' if not changed else f'{changed} counts changed.'}")
    return 0 if not changed else 1


def show_quarantine(settings: Settings, month: Month) -> int:
    path = settings.quarantine_month_dir(month) / "part-0.parquet"
    if not path.exists():
        print(f"No quarantine for {month}: run `make quality MES={month}` first")
        return 1
    con = duckdb.connect(config=duckdb_config())
    rows = con.execute(
        f"""WITH q AS (SELECT *, unnest(string_split(violated_rules, ';')) AS rule_id FROM read_parquet('{path.as_posix()}'))
            SELECT rule_id, count(*) OVER (PARTITION BY rule_id) AS rows_with_rule, violated_rules, source_file, source_row_number,
                   tpep_pickup_datetime, tpep_dropoff_datetime, trip_distance, total_amount, pu_location_id, do_location_id
            FROM q QUALIFY row_number() OVER (PARTITION BY rule_id ORDER BY source_row_number) = 1
            ORDER BY rule_id"""
    ).fetchall()
    columns = ["rule", "rows", "violated_rules", "source_file", "source_row", "pickup", "dropoff", "distance", "total", "pu", "do"]
    print(f"\nQuarantine {month} ({path}): one example per rule\n")
    for row in rows:
        print("  " + ", ".join(f"{c}={v}" for c, v in zip(columns, row)))
    print("\nThe raw file is untouched: source_file + source_row_number locate the original row.")
    return 0


def quality_report(settings: Settings, month: Month) -> int:
    path = settings.reports_dir / "quality" / f"quality_report_{month.label}.md"
    if not path.exists():
        print(f"No report for {month}: run `make quality MES={month}` first")
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0


def sql_statements(sql_text: str) -> list[tuple[str, str]]:
    """(title, statement) pairs of a SQL script.

    The title is the first line of the comment block right above the statement; a blank line ends
    a block, so a file header is not taken as a title. The Snowflake connector's splitter ignores ';'
    inside comments and string literals. A plain split(';') breaks on the comment that documents the
    query_tag format ('project=nyc_taxi;env=...').
    """
    from snowflake.connector.util_text import split_statements

    pairs = []
    for statement, _is_put_or_get in split_statements(io.StringIO(sql_text), remove_comments=False):
        lines = [line.strip() for line in statement.strip().splitlines()]
        start = next((i for i, line in enumerate(lines) if line and not line.startswith("--")), None)
        if start is None:  # comment-only chunk, nothing to run
            continue
        block = list(itertools.takewhile(lambda line: line.startswith("--"), reversed(lines[:start])))
        title = block[-1].lstrip("-").strip() if block else lines[start]
        pairs.append((title, statement.strip()))
    return pairs


def finops() -> int:
    from src.load_snowflake import snowflake_connect

    statements = sql_statements((ROOT / "snowflake" / "finops.sql").read_text(encoding="utf-8"))
    con = snowflake_connect(step="finops")
    try:
        for title, statement in statements:
            with con.cursor() as cur:
                cur.execute(statement)
                rows = cur.fetchall()
                print(f"\n== {title} ({len(rows)} rows)")
                print(" | ".join(d[0] for d in cur.description))
                for row in rows:
                    print(" | ".join("" if v is None else str(v) for v in row))
    finally:
        con.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("counts")
    c.add_argument("--label", required=True)
    c.add_argument("--compare")
    for name in ("show-quarantine", "quality-report"):
        sub.add_parser(name).add_argument("--mes", required=True)
    sub.add_parser("finops")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if args.command == "counts":
        return counts(settings, args.label, args.compare)
    if args.command == "show-quarantine":
        return show_quarantine(settings, Month.parse(args.mes))
    if args.command == "quality-report":
        return quality_report(settings, Month.parse(args.mes))
    return finops()


if __name__ == "__main__":
    sys.exit(main())
