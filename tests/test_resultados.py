"""Results in Spanish: rendering helpers, the README block and a whole report from a synthetic warehouse."""
from __future__ import annotations

import duckdb
import pytest

from src import interpretacion as interp
from src import resultados
from src.config import Month


def test_note_is_inline_for_one_paragraph_and_a_list_for_several_lines():
    assert resultados.note_markdown("Una sola línea.") == "**Interpretación:** Una sola línea."
    assert resultados.note_markdown("Primera.\nSegunda.\n") == "**Interpretación:**\n\n- Primera.\n- Segunda."
    assert resultados.PENDING in resultados.note_markdown("")


def test_readme_block_is_replaced_between_markers_only():
    readme = f"# Title\n\nbefore\n\n{resultados.README_START}\nold results\n{resultados.README_END}\n\nafter\n"
    block = f"{resultados.README_START}\nnew results\n{resultados.README_END}"

    updated = resultados.replace_block(readme, block)

    assert updated == f"# Title\n\nbefore\n\n{block}\n\nafter\n"
    assert resultados.replace_block(updated, block) == updated  # idempotent
    assert resultados.replace_block("# no markers\n", block) is None


def test_spanish_number_formats():
    assert interp.entero(3323437) == "3.323.437"
    assert interp.decimal(1234.5) == "1.234,50"
    assert interp.pct(15.76) == "15,8 %"
    assert interp.signo(15.76) == "+15,8 %" and interp.signo(-2.56) == "−2,6 %" and interp.signo(0.01) == "±0,0 %"
    assert interp.usd_millones(88_338_790) == "US$ 88,3 M"
    assert interp.hora(1) == "la 1:00" and interp.hora(18) == "las 18:00"
    assert interp.lista(["a", "b", "c"]) == "a, b y c"
    assert interp.mes_es(Month(2025, 2)) == "febrero 2025"


def test_one_results_file_per_month_in_the_folder_of_its_year():
    root = resultados.RESULTS_DIR
    assert resultados.results_file(Month(2025, 2)) == root / "2025" / "RESULTS_02.md"   # Feb 2025 vs Feb 2024
    assert resultados.results_file(Month(2026, 2)) == root / "2026" / "RESULTS_02.md"   # Feb 2026 vs Feb 2025
    assert resultados.results_file(Month(2025, 12)).name == "RESULTS_12.md"


# --- a whole report from a small warehouse (February 2025 vs February 2024, a leap year) ------------------------
ZONES = [(1, "EWR", "Newark Airport"), (132, "Queens", "JFK Airport"), (138, "Queens", "LaGuardia Airport"),
         (161, "Manhattan", "Midtown Center"), (237, "Manhattan", "Upper East Side South"),
         (61, "Brooklyn", "Crown Heights North"), (264, "Unknown", "N/A")]


def _synthetic_warehouse(path) -> None:
    con = duckdb.connect(str(path))
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE SCHEMA raw")
    con.execute("CREATE TABLE marts.dim_zone (location_id INTEGER, borough VARCHAR, zone VARCHAR, service_zone VARCHAR, is_airport BOOLEAN)")
    con.executemany("INSERT INTO marts.dim_zone VALUES (?, ?, ?, 'x', ?)",
                    [(i, b, z, z.endswith("Airport")) for i, b, z in ZONES])
    con.execute("""
        CREATE TABLE marts.fact_trips AS
        WITH base AS (
            SELECT y, i, CASE WHEN y = 2024 THEN 29 ELSE 28 END AS days
            FROM range(2400) AS r(i) CROSS JOIN (VALUES (2025), (2024)) AS t(y)
            WHERE i < CASE WHEN y = 2025 THEN 2400 ELSE 2000 END
        ), trips AS (
            SELECT y AS year, 2 AS month, i,
                   make_date(y, 2, CAST(i % days + 1 AS INTEGER)) AS pickup_date,
                   CAST((i * 7) % 24 AS INTEGER) AS pickup_hour,
                   CASE i % 10 WHEN 0 THEN 132 WHEN 1 THEN 138 WHEN 2 THEN 161 WHEN 3 THEN 161 WHEN 4 THEN 161
                               WHEN 5 THEN 237 WHEN 6 THEN 237 ELSE 61 END AS pu_location_id,
                   CASE i % 7 WHEN 0 THEN 132 ELSE 161 END AS do_location_id,
                   CASE WHEN y = 2025 AND i % 9 = 0 THEN 0 WHEN i % 5 = 0 THEN 2 WHEN i % 41 = 0 THEN 3
                        WHEN i % 43 = 0 THEN 4 ELSE 1 END AS payment_type
            FROM base
        ), measured AS (
            SELECT *, CASE WHEN pu_location_id = 132 THEN 2 ELSE 1 END AS ratecode_id,
                   1 + (i % 13) * 0.7 + CASE WHEN pu_location_id IN (132, 138) THEN 12 ELSE 0 END AS trip_distance
            FROM trips
        ), priced AS (
            SELECT *, CASE WHEN year = 2025 AND i = 17 THEN 9000.0 WHEN pu_location_id = 132 THEN 70.0
                           ELSE round(5 + trip_distance * 2.8, 2) END AS fare_amount
            FROM measured
        )
        SELECT year, month, pickup_date, pickup_hour, isodow(pickup_date) AS pickup_dow, pu_location_id, do_location_id,
               payment_type, ratecode_id, CASE WHEN payment_type = 0 THEN NULL ELSE 1 END AS passenger_count,
               trip_distance, trip_distance * 3 AS duration_min, fare_amount,
               CASE WHEN payment_type = 1 THEN round(fare_amount * 0.2, 2) ELSE 0 END AS tip_amount,
               CASE WHEN payment_type = 1 THEN 20.0 ELSE 0 END AS tip_pct,
               fare_amount + CASE WHEN payment_type = 1 THEN round(fare_amount * 0.2, 2) ELSE 0 END + 2.5 AS total_amount,
               CASE WHEN year = 2025 THEN CASE WHEN pu_location_id IN (161, 237) THEN 0.75 ELSE 0 END END AS cbd_congestion_fee
        FROM priced""")
    con.execute("""
        CREATE TABLE marts.agg_zone_hour AS
        SELECT pu_location_id, pickup_date, pickup_hour, year, month, count(*) AS trips,
               round(sum(total_amount), 2) AS total_revenue, round(avg(duration_min), 2) AS avg_duration_min
        FROM marts.fact_trips GROUP BY ALL""")
    con.execute("""
        CREATE TABLE marts.dim_date AS
        SELECT CAST(d AS DATE) AS date_key, year(d) AS year, month(d) AS month, day(d) AS day_of_month,
               isodow(d) AS day_of_week_iso, dayname(d) AS day_name
        FROM (SELECT unnest(generate_series(DATE '2024-02-01', DATE '2024-02-29', INTERVAL 1 DAY)) AS d
              UNION ALL SELECT unnest(generate_series(DATE '2025-02-01', DATE '2025-02-28', INTERVAL 1 DAY)))""")
    con.execute("CREATE TABLE raw.yellow_quarantine AS SELECT 2025 AS year, 2 AS month, 'R03' AS violated_rules FROM range(90) "
                "UNION ALL SELECT 2024, 2, 'R04' FROM range(40)")
    con.execute("CREATE TABLE marts.agg_quarantine_rule AS SELECT year, month, violated_rules AS rule_id, count(*) AS quarantined_rows "
                "FROM raw.yellow_quarantine GROUP BY ALL")
    con.close()


@pytest.fixture
def warehouse(settings):
    settings.warehouse_db.parent.mkdir(parents=True, exist_ok=True)
    _synthetic_warehouse(settings.warehouse_db)
    return settings


def test_report_is_written_from_the_numbers_of_the_run(warehouse, tmp_path):
    results_dir = tmp_path / "results"
    path = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=results_dir)

    assert path == results_dir / "2025" / "RESULTS_02.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Resultados: febrero 2025 vs febrero 2024")
    assert "`make all MES=2025-02 INGEST_MODE=direct WAREHOUSE=duckdb`" in text      # local mode command
    assert text.count("**Interpretación:**") == 6 and resultados.PENDING not in text
    assert "## Calidad de los datos y cuarentena" in text and "## Conclusiones" in text
    # numbers of this warehouse, in Spanish format
    assert "2.400 viajes válidos" in text and "+20,0 %" in text
    assert "(28 contra 29 días)" in text                                   # leap-year February
    assert "US$ 9.000,00" in text                                          # the outlier is named, not hidden
    assert "Flex Fare" in text                                             # only 2025 has payment type 0
    assert "En febrero 2024 la columna no existía" in text                 # CBD fee: NULL in the comparison year
    # quality: no control database here, so the counts come from the warehouse and say so
    assert "2025-02 | `yellow_tripdata_2025-02.parquet`" in text and "| 2.490 | 2.400 | 90 |" in text
    assert "conteos salen del warehouse" in text
    for leftover in ("None", "nan", "{", "}"):
        assert leftover not in text.split("## 1.")[0], leftover          # no template or Python leftovers
    assert "](../../sql/q1_top10_pickup_zones.sql)" in text               # links climb out of results/2025/
    assert list(tmp_path.glob("*.md")) == []                               # one file per month, nothing else


def test_a_month_before_the_cbd_toll_says_the_toll_did_not_exist(warehouse, tmp_path):
    con = duckdb.connect(str(warehouse.warehouse_db))
    con.execute("UPDATE marts.fact_trips SET cbd_congestion_fee = NULL")
    con.close()
    text = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path).read_text(encoding="utf-8")
    assert "todavía no existía" in text
