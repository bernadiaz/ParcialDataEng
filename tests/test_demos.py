"""SQL script splitting for `make finops` (no Snowflake connection needed)."""
from __future__ import annotations

from src.config import ROOT
from src.demos import sql_statements


def test_semicolons_in_comments_and_strings_do_not_split():
    script = (
        "-- header of the file; not a title\n"
        "\n"
        "-- Tagged queries (query_tag project=nyc_taxi;env=dev;step=load)\n"
        "-- a note about the query\n"
        "SELECT 'a;b' AS literal, query_tag\n"
        "FROM t WHERE query_tag LIKE 'project=nyc_taxi;%';\n"
        "\n"
        "-- trailing comment only\n"
    )
    pairs = sql_statements(script)

    assert len(pairs) == 1
    title, statement = pairs[0]
    assert title == "Tagged queries (query_tag project=nyc_taxi;env=dev;step=load)"
    assert "'a;b'" in statement and "LIKE 'project=nyc_taxi;%'" in statement


def test_finops_script_has_three_queries_with_titles():
    pairs = sql_statements((ROOT / "snowflake" / "finops.sql").read_text(encoding="utf-8"))

    assert [title.split(" (")[0].split(",")[0] for title, _ in pairs] == [
        "Credits per warehouse and day over the last 14 days",
        "Queries and elapsed time per pipeline step",
        "Storage of the project objects",
    ]
    assert all(statement.lstrip("-").strip() and "SELECT" in statement for _, statement in pairs)
