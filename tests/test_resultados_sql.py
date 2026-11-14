"""Smoke: SQL de preguntas renderiza y es ejecutable contra el warehouse si existe."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.config import ROOT, get_settings
from src.modelo import warehouse_path
from src.resultados import SQL_DIR, render_sql


def test_all_question_sql_files_exist():
    expected = [
        "q1_top_zones_variation.sql",
        "q2_peak_hour_avg_revenue.sql",
        "q3_cbd_fee_share.sql",
        "q3b_cbd_top_zones.sql",
        "q4_tip_pct_by_payment.sql",
        "q5_airport_trips.sql",
        "q6_month_variation.sql",
    ]
    for name in expected:
        assert (SQL_DIR / name).exists()


def test_render_sql_substitutes_months():
    sql = render_sql(
        SQL_DIR / "q6_month_variation.sql",
        {
            "target_year": 2025,
            "target_month": 3,
            "compare_year": 2024,
            "compare_month": 3,
        },
    )
    assert "{{" not in sql
    assert "2025" in sql and "2024" in sql


@pytest.mark.skipif(
    not (ROOT / "data" / "warehouse" / "nyc_taxi.duckdb").exists(),
    reason="warehouse no generado aún",
)
def test_q1_runs_on_warehouse():
    settings = get_settings(mes="2025-03")
    wh = warehouse_path(settings)
    sql = render_sql(
        SQL_DIR / "q1_top_zones_variation.sql",
        {
            "target_year": 2025,
            "target_month": 3,
            "compare_year": 2024,
            "compare_month": 3,
        },
    )
    con = duckdb.connect(str(wh), read_only=True)
    rows = con.execute(sql).fetchall()
    assert len(rows) == 10
