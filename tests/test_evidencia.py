"""Evidence of the reports: the chart catalog, the dbt evidence models, the audit of every figure and the quality reports
in the warehouse."""
from __future__ import annotations

import re

import duckdb
import pytest

from src import calidad, load_snowflake, resultados
from src import evidencia as ev
from src import interpretacion as interp
from src.config import Month
from tests import synthetic
from tests.conftest import JAN_2025, trip, write_tlc_parquet

FEB = Month(2025, 2)


@pytest.fixture
def warehouse(settings):
    synthetic.warehouse(settings)
    synthetic.publish_reports(settings)
    return settings


@pytest.fixture
def run(warehouse):
    """Queries on the warehouse, with the pipeline's own connection."""
    con = resultados.open_connection(warehouse)
    yield lambda sql: resultados.run_query(warehouse, sql, con)
    con.close()


# --- one set of thresholds ------------------------------------------------------------------------------------------
def test_dbt_and_python_use_the_same_thresholds():
    dbt = synthetic.dbt_vars()
    params, _ = calidad.load_rules()
    assert dbt["fare_cap"] == interp.FARE_CAP
    assert dbt["stable_pct"] == interp.STABLE_PCT
    assert str(params["cbd_fee_start"]).startswith(str(dbt["cbd_fee_start"]))
    question = (synthetic.ROOT / "sql" / "q3_cbd_fee_share.sql").read_text(encoding="utf-8")
    assert f"b.trips >= {dbt['cbd_min_zone_trips']}" in question


# --- catalog -------------------------------------------------------------------------------------------------------
def test_chart_codes_and_anchors_are_unique():
    charts = [*ev.CATALOGO, *ev.ANUALES]
    assert len({g.codigo for g in charts}) == len(charts)
    assert len({g.componente for g in charts}) == len(charts)
    assert len({g.titulo for g in ev.CATALOGO}) == len(ev.CATALOGO)
    assert {g.pestana for g in ev.CATALOGO} == {k for k, _ in ev.PESTANAS}
    assert {g.pestana for g in ev.ANUALES} == {k for k, _ in ev.PESTANAS_ANUALES}


def test_every_citation_is_a_chart_of_the_monthly_dashboard():
    monthly = {g.codigo for g in ev.CATALOGO}
    for block, codes in ev.CITAS.items():
        assert codes and set(codes) <= monthly, block


def test_every_chart_reads_columns_that_its_table_has(run):
    for grafico in (*ev.CATALOGO, *ev.ANUALES):
        columns = set(run(f"select * from marts.{grafico.tabla} limit 0")[0])
        used = {*grafico.columnas_datos, *(c for c, _ in grafico.orden), *(c for c, _, _ in grafico.filtro)}
        assert used <= columns, (grafico.codigo, used - columns)
        assert {c for c, _ in grafico.formatos} - {"y"} <= columns, grafico.codigo


def test_the_filter_in_python_and_in_sql_select_the_same_rows(run):
    evidence = ev.leer(run, FEB)
    for grafico in ev.CATALOGO:
        where = f" and {ev.filtro_sql(grafico.filtro)}" if grafico.filtro else ""
        _, rows = run(f"select count(*) from marts.{grafico.tabla} where mes = '{FEB.label}'{where}")
        assert rows[0][0] == len(grafico.filas(evidence)), grafico.codigo


# --- evidence models -----------------------------------------------------------------------------------------------
def test_the_evidence_has_the_twelve_months_of_the_year_and_says_which_are_missing(run):
    _, rows = run("select mes, estado from marts.ev_cobertura where anio = 2025 order by mes_num")
    assert [m for m, _ in rows] == [f"2025-{n:02d}" for n in range(1, 13)]
    assert dict(rows)["2025-02"] == "comparado" and dict(rows)["2025-03"] == "mes sin cargar"
    _, rows = run("select estado from marts.ev_cobertura where mes = '2024-02'")
    assert rows == [("falta el mes del año anterior",)]


def test_only_months_with_both_years_are_comparable(run):
    assert ev.meses_comparables(run) == [FEB]
    assert ev.meses_comparables(run, 2024) == []
    assert not ev.leer(run, Month(2024, 2)).existe
    _, per_month = ev.leer_anio(run, 2025)
    assert [m for m, e in per_month.items() if e.existe] == ["2025-02"]


def test_indicators_are_the_figures_of_the_trips(run):
    evidence = ev.leer(run, FEB)
    _, rows = run("select count(*), sum(total_amount), avg(fare_amount), median(fare_amount) from marts.fact_trips where year = 2025")
    trips, revenue, fare, median = rows[0]
    assert evidence.indicador("viajes")["valor_mes"] == trips == 2400
    assert evidence.indicador("viajes")["variacion_pct"] == pytest.approx(20.0)
    assert evidence.indicador("recaudacion")["valor_mes"] == pytest.approx(revenue)
    assert evidence.indicador("tarifa_media")["valor_mes"] == pytest.approx(fare)
    assert evidence.indicador("tarifa_mediana")["valor_mes"] == pytest.approx(median)
    assert evidence.indicador("pct_con_peaje")["valor_anterior"] is None       # NULL, not 0: the toll did not exist
    with pytest.raises(KeyError):
        evidence.indicador("no_existe")


def test_the_toll_start_splits_its_month(settings):
    synthetic.warehouse(settings, month=1)                                       # January 2025: the toll starts on the 5th
    con = duckdb.connect(str(settings.warehouse_db), read_only=True)
    rows = dict(con.execute("select indicador_id, valor_mes from marts.ev_indicadores where mes = '2025-01' and grupo = 'peaje'").fetchall())
    before = con.execute("select 100.0 * count(*) / 2400 from marts.fact_trips where year = 2025 and day(pickup_date) < 5").fetchone()[0]
    con.close()
    assert rows["pct_viajes_antes_peaje"] == pytest.approx(before)
    assert rows["pct_con_peaje_antes"] is not None and rows["pct_con_peaje_desde"] is not None


# --- audit ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("En enero 2025 hicieron 3.323.437 viajes, +15,8 % que en 2024, US$ 88,3 M", [3323437, 15.8, 88.3]),
    ("cae −2,6 % y baja a US$ 17,47", [2.6, 17.47]),
    ("la regla R05 y la R10, `payment_type` 2025-01, payment_type 0, RatecodeID 2, top 10", []),
    ("sin las tarifas mayores a US$ 500 y con más de 10 millas (del 7,8 % al 6,8 %)", [7.8, 6.8]),
    ("empezó el 5 de enero: del 1 al 4 (10,4 %) y desde el 5 lo paga el 73,6 %", [10.4, 73.6]),
    ("el 20,8 % de sus viajes, el 94 % deja propina", [20.8, 94]),
    ("a las 5:00 y a la 1:00", [5, 1]),
    ("queda en NULL, no en 0; casi 0 %", []),
])
def test_figures_of_a_spanish_text(text, expected):
    assert [value for _, _, value, _, _ in ev.numeros(text)] == expected


def test_a_figure_matches_a_cell_with_its_rounding_and_its_sign():
    assert ev.coincide(15.763, "+", 15.8, 1, 1.0) and not ev.coincide(15.763, "+", 15.7, 1, 1.0)
    assert ev.coincide(-2.556, "-", 2.6, 1, 1.0) and not ev.coincide(2.556, "-", 2.6, 1, 1.0)
    assert ev.coincide(-10.37, "", 10.4, 1, 1.0)                                 # "cae un 10,4 %"
    assert ev.coincide(88_338_790.47, "", 88.3, 1, 1e6)                          # US$ 88,3 M


def test_the_audit_finds_an_altered_figure_and_a_block_without_charts(warehouse, run, tmp_path):
    path = resultados.write_report(warehouse, FEB, readme=None, results_dir=tmp_path).path
    evidence, text = ev.leer(run, FEB), path.read_text(encoding="utf-8")
    assert all(c.respaldada for c in ev.auditar(text, evidence))

    altered = text.replace("2.400 viajes válidos", "2.401 viajes válidos", 1)
    assert [c.texto for c in ev.auditar(altered, evidence) if not c.respaldada] == ["2.401"]

    orphan = text.replace("\n## Conclusiones\n", "\n## Conclusiones\n\nUn dato suelto: 12.345 viajes.\n\n## Otra\n", 1)
    unbacked = [c for c in ev.auditar(orphan, evidence) if not c.respaldada]
    assert [(c.texto, c.citados) for c in unbacked] == [("12.345", ())]


def test_the_audit_only_looks_in_the_charts_the_block_cites(warehouse, run, tmp_path):
    text = resultados.write_report(warehouse, FEB, readme=None, results_dir=tmp_path).path.read_text(encoding="utf-8")
    evidence = ev.leer(run, FEB)
    moved = re.sub(r"(> .*\n\n)\*\*Respaldo en Superset:\*\*.*", r"\1**Respaldo en Superset:** [EC.4 Contrato][EC.4]", text, count=1)
    unbacked = [c for c in ev.auditar(moved, evidence) if not c.respaldada]
    assert unbacked and {c.seccion for c in unbacked} == {"Resumen"}             # EC.4 shows no trips


def test_counts_written_with_words_are_checked_too(warehouse, run):
    evidence = ev.leer(run, FEB)
    assert ev.contrastes({"top10_manhattan": 2, "top10_crecen": int(evidence.indicador("top10_crecen")["valor_mes"])}, evidence) == []
    assert "top10_manhattan" in ev.contrastes({"top10_manhattan": 9}, evidence)[0]


def test_the_verification_block_is_replaced_in_place():
    text = f"a\n{ev.bloque_verificacion('viejo')}\nb\n"
    assert ev.reemplazar_verificacion(text, "nuevo") == f"a\n{ev.bloque_verificacion('nuevo')}\nb\n"
    assert ev.reemplazar_verificacion("sin bloque", "nuevo") is None


# --- dashboards of each engine -----------------------------------------------------------------------------------------
def test_local_and_cloud_reports_have_their_own_dashboards(settings, monkeypatch):
    from dataclasses import replace

    cloud = replace(settings, warehouse="snowflake", ingest_mode="hybrid")
    assert ev.slug_mes(settings, FEB) == "respaldo-local-2025-02" and ev.slug_mes(cloud, FEB) == "respaldo-nube-2025-02"
    assert ev.slug_anio(settings, 2025) == "respaldo-local-2025"
    assert ev.argumentos_make(cloud, FEB) == "MES=2025-02"
    assert ev.argumentos_make(settings, FEB) == "MES=2025-02 INGEST_MODE=direct WAREHOUSE=duckdb"


def test_the_links_of_the_report_open_in_a_browser(monkeypatch):
    from src import dashboards

    monkeypatch.setenv("SUPERSET_URL", "http://superset:8088")                   # the address inside the pipeline container
    monkeypatch.setenv("SUPERSET_PORT", "8095")
    assert dashboards.superset_public_url() == "http://localhost:8095"
    monkeypatch.setenv("SUPERSET_URL", "http://localhost:8090/")
    assert dashboards.superset_public_url() == "http://localhost:8090"


# --- quality and schema reports in the warehouse -------------------------------------------------------------------------
def _tables(settings, sql):
    con = duckdb.connect(str(settings.warehouse_db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_the_loader_publishes_the_quality_reports_and_replaces_them(settings, zones_file):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip(), trip(trip_distance=0), trip(passenger_count=None)])
    calidad.run_month(settings, JAN_2025)
    for _ in range(2):
        load_snowflake.load_months(settings, [JAN_2025])
    assert _tables(settings, "select year, month, rows_read, rows_accepted, rows_quarantined, rows_with_warnings, reconciled "
                             "from raw.quality_summary") == [(2025, 1, 3, 2, 1, 1, True)]
    rules = dict(_tables(settings, "select rule_id, violations from raw.quality_rules"))
    assert len(rules) == 10 and rules["R03"] == 1 and rules["R05"] == 1 and rules["R04"] == 0
    assert _tables(settings, "select description from raw.quality_rules where rule_id = 'R03'")[0][0].startswith("Distancia")


def test_the_loader_publishes_months_loaded_before_this_version(settings, zones_file):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip()])
    calidad.run_month(settings, JAN_2025)
    load_snowflake.load_months(settings, [JAN_2025], include_quality=False)     # as the earlier version did
    warehouse = load_snowflake.open_warehouse(settings)
    try:
        assert load_snowflake.unpublished_quality(settings, warehouse) == [JAN_2025]
        load_snowflake.load_quality(settings, warehouse, [])
        assert load_snowflake.unpublished_quality(settings, warehouse) == []
        warehouse.conn.execute("DELETE FROM raw.quality_summary")
        warehouse.conn.execute("UPDATE raw.load_log SET rows_loaded = 99")      # the report is of other rows: left out
        assert load_snowflake.unpublished_quality(settings, warehouse) == []
    finally:
        warehouse.close()


def test_a_file_that_matches_the_contract_has_one_finding():
    assert load_snowflake.schema_findings({}) == [("none", None, None, None)]
    assert load_snowflake.schema_findings({"missing_optional": ["cbd_congestion_fee"], "cast_failures": {"passenger_count": 3}}) == [
        ("missing_optional", "cbd_congestion_fee", None, None), ("cast_failure", "passenger_count", None, 3)]


class _Cursor:
    def __init__(self, log):
        self.log, self.rowcount, self.description = log, 0, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.log.append(sql.split()[0])

    def executemany(self, sql, rows):
        self.log.append(f"INSERT x{len(rows)}")
        if any(len(r) != sql.count("%s") for r in rows):
            raise AssertionError("values do not match the columns")

    def fetchall(self):
        return []


class _Connection:
    def __init__(self, fail_on: str = ""):
        self.log: list[str] = []

    def cursor(self):
        return _Cursor(self.log)

    def close(self):
        pass


def test_snowflake_replaces_the_quality_reports_of_a_month_in_one_transaction(settings, zones_file):
    write_tlc_parquet(settings.raw_month_dir(JAN_2025) / "f.parquet", [trip()])
    calidad.run_month(settings, JAN_2025)
    conn = _Connection()
    load_snowflake.SnowflakeWarehouse(connection=conn).replace_quality(JAN_2025, load_snowflake.quality_tables(settings, JAN_2025))
    assert conn.log == ["BEGIN", "DELETE", "INSERT x1", "DELETE", "INSERT x10", "DELETE", "INSERT x1", "COMMIT"]

    conn = _Connection()
    with pytest.raises(AssertionError):
        load_snowflake.SnowflakeWarehouse(connection=conn).replace_quality(JAN_2025, {"quality_summary": [(1, 2)]})
    assert conn.log[-1] == "ROLLBACK"
