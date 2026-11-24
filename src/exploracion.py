"""Exploration behind the fixed thresholds (plan step 4): R03 max distance and the own rule R09.

Reads the raw month (before any rule), so the numbers show why each threshold was chosen.
Writes data/reports/exploration/exploration_<mes>.md.

    python -m src.exploracion --mes 2025-01 --mes 2024-01
"""
from __future__ import annotations

import argparse
import sys

import duckdb

from src import esquema
from src.calidad import load_rules
from src.config import Month, Settings, configure_duckdb, get_logger, track_step

log = get_logger("exploracion")

QUERIES = {
    "Distance distribution (miles)": """
        SELECT quantile_cont(trip_distance, 0.50) AS p50, quantile_cont(trip_distance, 0.99) AS p99,
               quantile_cont(trip_distance, 0.999) AS p999, max(trip_distance) AS max,
               count(*) FILTER (WHERE trip_distance <= 0) AS rows_le_0,
               count(*) FILTER (WHERE trip_distance > 50) AS rows_gt_50,
               count(*) FILTER (WHERE trip_distance > {max_trip_distance_miles}) AS rows_gt_max
        FROM yellow_src""",
    "Rate code of trips above the max distance": """
        SELECT ratecode_id, count(*) AS trips, round(avg(total_amount), 2) AS avg_total
        FROM yellow_src WHERE trip_distance > {max_trip_distance_miles} GROUP BY 1 ORDER BY 2 DESC""",
    "Average speed (mph) of trips with positive duration": """
        WITH s AS (SELECT trip_distance / (date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) / 3600.0) AS mph
                   FROM yellow_src WHERE tpep_dropoff_datetime > tpep_pickup_datetime AND trip_distance > 0)
        SELECT quantile_cont(mph, 0.99) AS p99, quantile_cont(mph, 0.999) AS p999,
               count(*) FILTER (WHERE mph > {max_avg_speed_mph}) AS rows_gt_max, max(mph) AS max FROM s""",
    "Flex Fare (payment_type 0) and missing metadata": """
        SELECT count(*) FILTER (WHERE payment_type = 0) AS flex_fare_trips,
               count(*) FILTER (WHERE passenger_count IS NULL) AS passenger_null,
               count(*) FILTER (WHERE ratecode_id IS NULL) AS ratecode_null,
               round(100.0 * count(*) FILTER (WHERE payment_type = 0) / count(*), 2) AS pct_flex
        FROM yellow_src""",
    "CBD congestion fee values": """
        SELECT cbd_congestion_fee, count(*) AS trips,
               count(*) FILTER (WHERE tpep_pickup_datetime < TIMESTAMP '{cbd_fee_start}') AS before_start
        FROM yellow_src GROUP BY 1 ORDER BY 2 DESC LIMIT 6""",
    "Tip vs fare": """
        SELECT count(*) FILTER (WHERE tip_amount < 0) AS tip_negative,
               count(*) FILTER (WHERE tip_amount > fare_amount) AS tip_gt_fare,
               count(*) FILTER (WHERE tip_amount > fare_amount AND fare_amount > 0) AS tip_gt_positive_fare
        FROM yellow_src""",
}


def explore(settings: Settings, month: Month) -> str:
    params, _ = load_rules()
    con = configure_duckdb(duckdb.connect(), settings)
    esquema.register_yellow_month(con, settings, month, esquema.load_contract(esquema.YELLOW_CONTRACT))
    lines = [f"# Exploration - {month.label}", "", "Raw month, before the quality rules.", ""]
    for title, sql in QUERIES.items():
        cursor = con.execute(sql.format(**params))
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        lines += [f"## {title}", "", "| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
        lines += ["| " + " | ".join("" if v is None else (f"{v:,.2f}" if isinstance(v, float) else str(v)) for v in row) + " |" for row in rows]
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", action="append", required=True)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    out_dir = settings.reports_dir / "exploration"
    out_dir.mkdir(parents=True, exist_ok=True)
    for value in args.mes:
        month = Month.parse(value)
        with track_step(settings, "explore", month.label):
            path = out_dir / f"exploration_{month.label}.md"
            path.write_text(explore(settings, month), encoding="utf-8")
            log.info("wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
