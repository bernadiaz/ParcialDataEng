"""Results in Spanish: rendering helpers, the README block, a whole report from a synthetic warehouse and the months
that cannot be compared."""
from __future__ import annotations

import duckdb
import pytest

from src import evidencia as ev
from src import interpretacion as interp
from src import orchestration, resultados
from src.config import Month
from tests import synthetic


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
@pytest.fixture
def warehouse(settings):
    synthetic.warehouse(settings)
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
    # quality: no quality report was published here, so the counts come from the warehouse and the text says so
    assert "2025-02 | `yellow_tripdata_2025-02.parquet`" in text and "| 2.490 | 2.400 | 90 |" in text
    assert "conteos salen del warehouse" in text
    for leftover in ("None", "nan", "{", "}"):
        assert leftover not in text.split("## 1.")[0], leftover          # no template or Python leftovers
    assert "](../../sql/q1_top10_pickup_zones.sql)" in text               # links climb out of results/2025/
    assert list(tmp_path.glob("*.md")) == []                               # one file per month, nothing else


def test_the_quality_reports_published_by_the_loader_are_the_ones_of_the_report(warehouse, tmp_path):
    synthetic.publish_reports(warehouse)
    report = resultados.write_report(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    text = report.path.read_text(encoding="utf-8")
    assert "| 2.490 | 2.490 | 2.400 | 90 | 3,61 % | 300 (12,05 %) | sí |" in text    # with the warnings of the report
    assert "conteos salen del warehouse" not in text
    assert "no trae `cbd_congestion_fee`" in text and "7 valores no se pudieron convertir" in text
    assert not report.sin_respaldo


def test_a_quality_report_of_other_rows_is_not_used(warehouse, tmp_path):
    synthetic.publish_reports(warehouse)
    con = duckdb.connect(str(warehouse.warehouse_db))
    con.execute("UPDATE raw.quality_summary SET rows_accepted = 1, rows_read = 91 WHERE year = 2025")  # another run of the month
    con.close()
    synthetic.rebuild(warehouse)
    text = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path).read_text(encoding="utf-8")
    assert "| 2.490 | 2.400 | 90 | 3,61 % | - | sí |" in text               # the warehouse wins, and it has no warnings
    assert "conteos salen del warehouse" in text


def test_a_month_before_the_cbd_toll_says_the_toll_did_not_exist(warehouse, tmp_path):
    con = duckdb.connect(str(warehouse.warehouse_db))
    con.execute("UPDATE marts.fact_trips SET cbd_congestion_fee = NULL")
    con.close()
    synthetic.rebuild(warehouse)
    report = resultados.write_report(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    assert "todavía no existía" in report.path.read_text(encoding="utf-8")
    assert not report.sin_respaldo


# --- every block says which charts back it -----------------------------------------------------------------------
def test_every_block_of_the_report_cites_its_charts(warehouse, tmp_path):
    report = resultados.write_report(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    text = report.path.read_text(encoding="utf-8")
    for question in range(1, 7):
        section = text.split(f"\n## {question}. ")[1].split("\n## ")[0]
        assert section.count("**Respaldo en Superset:**") >= 1, question
    conclusions = text.split("\n## Conclusiones\n")[1].split("\n## ")[0]
    bullets = [line for line in conclusions.splitlines() if line.startswith("- ")]
    assert len(bullets) == conclusions.count("  - _Respaldo:_ ") == 5        # one set of charts per conclusion
    assert "[E1.1]: http://localhost:8090/superset/dashboard/respaldo-local-2025-02/#CHART-E1-1" in text
    for code in {c for codes in ev.CITAS.values() for c in codes}:
        assert f"\n[{code}]: " in text, code                                  # every cited chart has its address
    assert report.cifras and not report.sin_respaldo and not report.avisos
    assert f"{len(report.cifras)} números en este reporte, {len(report.cifras)} se ven en los charts" in text


def test_a_rerun_replaces_the_report_of_its_month_and_leaves_the_others_alone(warehouse, tmp_path):
    other = tmp_path / "2025" / "RESULTS_01.md"
    other.parent.mkdir(parents=True)
    other.write_text("el reporte de enero", encoding="utf-8")
    first = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path).read_text(encoding="utf-8")
    second = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path).read_text(encoding="utf-8")

    def without_run(text: str) -> str:
        return "\n".join(line for line in text.splitlines() if not line.startswith("| Corrida"))

    assert without_run(first) == without_run(second)
    assert other.read_text(encoding="utf-8") == "el reporte de enero"
    assert sorted(p.name for p in (tmp_path / "2025").iterdir()) == ["RESULTS_01.md", "RESULTS_02.md"]


def test_the_report_is_not_written_when_the_questions_and_the_evidence_differ(warehouse, tmp_path):
    path = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    before = path.read_text(encoding="utf-8")
    con = duckdb.connect(str(warehouse.warehouse_db))
    con.execute("UPDATE marts.ev_zonas SET viajes_mes = viajes_mes + 1 WHERE puesto_mes = 1")
    con.close()
    with pytest.raises(ev.EvidenciaError, match="q1 puesto 1"):
        resultados.write_report(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    assert path.read_text(encoding="utf-8") == before


# --- months that cannot be compared: the report says so, with no figures --------------------------------------------
def test_a_month_without_its_comparison_month_gets_a_report_without_figures(warehouse, tmp_path):
    report = resultados.write_report(warehouse, Month(2024, 2), readme=None, results_dir=tmp_path)   # 2023-02 is not loaded
    text = report.path.read_text(encoding="utf-8")
    assert not report.disponible and report.path == tmp_path / "2024" / "RESULTS_02.md"
    assert "Sin comparación: no hay viajes aceptados de febrero 2023 en el warehouse." in text
    assert "## Conclusiones" not in text and "**Interpretación:**" not in text and "%" not in text
    assert not resultados.has_figures(report.path)

    resultados.write_report(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    assert resultados.has_figures(tmp_path / "2025" / "RESULTS_02.md")


def test_a_report_with_figures_is_never_replaced_by_one_without_them(warehouse, tmp_path):
    path = resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path)
    before = path.read_text(encoding="utf-8")
    resultados.write_unavailable(warehouse, Month(2025, 2), "la TLC no responde", tmp_path)
    assert path.read_text(encoding="utf-8") == before


def test_a_report_without_figures_is_replaced_when_the_month_can_be_compared(warehouse, tmp_path):
    path = resultados.write_unavailable(warehouse, Month(2025, 2), "la TLC todavía no publicó febrero 2025", tmp_path).path
    assert "la TLC todavía no publicó febrero 2025" in path.read_text(encoding="utf-8")
    assert resultados.write_results(warehouse, Month(2025, 2), readme=None, results_dir=tmp_path) == path
    assert resultados.has_figures(path)


@pytest.fixture
def written(monkeypatch):
    """Reports without figures that `make all` writes before running anything (month, reason)."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(resultados, "write_unavailable", lambda settings, month, reason: calls.append((month.label, reason)))
    return calls


def test_make_all_explains_in_the_report_why_a_month_cannot_run(settings, written, monkeypatch):
    monkeypatch.setattr(orchestration, "month_published", lambda month: False)
    assert orchestration.check_months("2025-10") is None                       # not published by the TLC yet
    assert orchestration.check_months("2009-05") is None                       # no month of 2008 to compare with
    assert [m for m, _ in written] == ["2025-10", "2009-05"]
    assert "la TLC todavía no publicó octubre 2025" in written[0][1] and "mayo 2008" in written[1][1]


def test_make_all_does_not_create_reports_for_typos_or_years_that_have_not_started(settings, written):
    for mes in ("2025-13", "febrero", "2099-01", "2008-12"):
        assert orchestration.check_months(mes) is None
    assert written == []


def test_make_all_explains_a_month_of_this_year_that_has_not_started(settings, written, monkeypatch):
    class Today(orchestration.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 6, 15, tzinfo=tz)

    import src.config as config

    monkeypatch.setattr(orchestration, "datetime", Today)
    monkeypatch.setattr(config, "datetime", Today)
    assert orchestration.check_months("2025-09") is None
    assert written == [("2025-09", "septiembre 2025 todavía no empezó")]


def test_make_all_year_runs_the_12_months_and_goes_on_after_one_that_cannot_run(settings, monkeypatch, capsys):
    ran: list[str] = []

    def fake_call(cmd, cwd=None, env=None):
        ran.append(cmd[-1])
        assert "RUN_ID" not in env                                              # each month is its own run
        return 2 if cmd[-1] >= "2026-10" else 0

    monkeypatch.setenv("RUN_ID", "outer")
    monkeypatch.setattr(orchestration.subprocess, "call", fake_call)
    assert orchestration.run_year(2026) == 0
    assert ran == [f"2026-{m:02d}" for m in range(1, 13)]
    assert "without data yet: 2026-10, 2026-11, 2026-12" in capsys.readouterr().out

    monkeypatch.setattr(orchestration.subprocess, "call", lambda *a, **k: 1)
    assert orchestration.run_year(2026) == 1                                    # a failed month is not hidden
