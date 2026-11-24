"""Evidence dashboards: provisioning and verification against a Superset double that keeps its objects in memory and answers
chart/data with real queries on the synthetic warehouse."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import replace

import duckdb
import httpx
import pytest

from src import dashboards, orchestration, respaldo, resultados
from src import evidencia as ev
from src.config import Month
from tests import synthetic

FEB = Month(2025, 2)


class FakeSuperset:
    """The endpoints of the Superset REST API that the pipeline uses."""

    def __init__(self, warehouse_db, upper: bool = False):
        self.db, self.upper = warehouse_db, upper          # upper: column names as Snowflake returns them
        self.objects: dict[str, dict[int, dict]] = {k: {} for k in ("database", "dataset", "chart", "dashboard")}
        self.links: dict[int, set[int]] = {}               # dashboard -> charts
        self.calls: Counter = Counter()
        self.next_id = 1
        self.lie: dict[str, float] = {}                    # column -> value that chart/data answers instead of the real one

    def api(self) -> dashboards.SupersetAPI:
        api = object.__new__(dashboards.SupersetAPI)
        api.http = httpx.Client(base_url="http://superset.test", transport=httpx.MockTransport(self.handle))
        return api

    def sql(self, query: str) -> tuple[list[str], list[tuple]]:
        con = duckdb.connect(str(self.db), read_only=True)
        try:
            cursor = con.execute(query)
            return [d[0] for d in cursor.description], cursor.fetchall()
        finally:
            con.close()

    def dashboard(self, key: str) -> dict | None:
        return next((d for d in self.objects["dashboard"].values() if key in (d.get("slug"), str(d["id"]))), None)

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1/")
        body = json.loads(request.content) if request.content else {}
        self.calls[f"{request.method} {path.split('/')[0]}"] += 1
        if path == "chart/data":
            return self.chart_data(body)
        if m := re.fullmatch(r"dashboard/([^/]+)/charts", path):
            found = self.dashboard(m[1])
            return httpx.Response(200, json={"result": [
                {"id": i, "slice_name": self.objects["chart"][i]["slice_name"], "form_data": json.loads(self.objects["chart"][i]["params"])}
                for i in sorted(self.links.get(found["id"], set()))]})
        if m := re.fullmatch(r"dataset/(\d+)/refresh", path):
            return httpx.Response(200, json={})
        if m := re.fullmatch(r"dataset/(\d+)", path):
            if request.method == "PUT":
                self.objects["dataset"][int(m[1])].update(body)
                return httpx.Response(200, json={})
            columns, _ = self.sql(self.objects["dataset"][int(m[1])]["sql"] + " limit 0")
            return httpx.Response(200, json={"result": {"columns": [
                {"column_name": c.upper() if self.upper else c} for c in columns]}})
        if m := re.fullmatch(r"dashboard/([^/]+)", path):
            found = self.dashboard(m[1])
            if found is None:
                return httpx.Response(404, json={})
            if request.method == "PUT":
                metadata = json.loads(body.pop("json_metadata", "{}"))
                positions = metadata.pop("positions", None)
                if positions is not None:
                    found["position_json"] = json.dumps(positions)
                    self.links[found["id"]] = {v["meta"]["chartId"] for v in positions.values()
                                               if isinstance(v, dict) and v.get("type") == "CHART"}
                found.update(body | {"json_metadata": json.dumps(metadata)})
            return httpx.Response(200, json={"result": found})
        if m := re.fullmatch(r"(database|dataset|chart|dashboard)/(\d+)", path):
            if request.method == "DELETE":
                self.objects[m[1]].pop(int(m[2]))
            else:
                self.objects[m[1]][int(m[2])].update(body)
            return httpx.Response(200, json={})
        if m := re.fullmatch(r"(database|dataset|chart|dashboard)/", path):
            if request.method == "POST":
                new = {"id": self.next_id, **body}
                self.objects[m[1]][self.next_id] = new
                self.next_id += 1
                return httpx.Response(201, json={"id": new["id"]})
            page = int(re.search(r"page:(\d+)", request.url.params["q"])[1])
            items = list(self.objects[m[1]].values())
            return httpx.Response(200, json={"count": len(items), "result": items[page * 100:(page + 1) * 100]})
        raise AssertionError(f"unexpected call {request.method} {path}")

    def chart_data(self, body: dict) -> httpx.Response:
        dataset = self.objects["dataset"][body["datasource"]["id"]]
        query = body["queries"][0]
        conditions = []
        for f in query["filters"]:
            values = ", ".join(str(v) if isinstance(v, int) else f"'{v}'" for v in f["val"])
            conditions.append(f"{f['col']} IN ({values})")
        if query["extras"]["where"]:
            conditions.append(query["extras"]["where"])
        metrics = query.get("metrics")
        select = list(query["columns"]) + [f"{m['sqlExpression']} AS \"{m['label']}\"" for m in metrics or []]
        sql = f"select {', '.join(select)} from ({dataset['sql']}) where {' and '.join(conditions) or 'true'}"
        if metrics is not None and query["columns"]:
            sql += f" group by {', '.join(query['columns'])}"
        columns, rows = self.sql(sql)
        names = [c.upper() if self.upper and c in query["columns"] else c for c in columns]
        data = [{n: self.lie.get(c.lower(), v) for n, c, v in zip(names, columns, row)} for row in rows]
        return httpx.Response(200, json={"result": [{"data": data, "error": None}]})


@pytest.fixture
def superset(settings, tmp_path, monkeypatch):
    """The synthetic warehouse, a Superset double on it and results/ in a temporary folder."""
    synthetic.warehouse(settings)
    synthetic.publish_reports(settings)
    fake = FakeSuperset(settings.warehouse_db)
    results = tmp_path / "results"
    monkeypatch.setattr(respaldo, "conectar_superset", fake.api)
    monkeypatch.setattr(respaldo, "database_payload", lambda s, m, export=True: ({"database_name": f"NYC Taxi ({s.warehouse})"}, "marts"))
    real = resultados.results_file
    monkeypatch.setattr(resultados, "results_file", lambda month, results_dir=results: real(month, results))
    fake.results = results
    return fake


def _slugs(fake: FakeSuperset) -> list[str]:
    return sorted(d["slug"] for d in fake.objects["dashboard"].values())


def _markdown(fake: FakeSuperset, slug: str) -> list[str]:
    position = json.loads(fake.dashboard(slug)["position_json"])
    return [v["meta"]["code"] for v in position.values() if isinstance(v, dict) and v.get("type") == "MARKDOWN"]


def _report(settings, superset):
    return resultados.write_report(settings, FEB, readme=None, results_dir=superset.results).path


def test_the_dashboards_of_the_year_are_built_and_match_the_report(settings, superset):
    path = _report(settings, superset)
    assert "pendiente" in ev.estado_verificacion(path)                            # not compared with Superset yet

    summary = respaldo.build(settings, FEB)

    assert summary["ok"], summary["diferencias"]
    assert _slugs(superset) == ["respaldo-local-2025", "respaldo-local-2025-02"]   # the only comparison loaded, and the year
    assert len(superset.objects["chart"]) == len(ev.CATALOGO) + len(ev.ANUALES)
    assert len(superset.objects["dataset"]) == len(ev.TABLAS)
    assert "Verificación contra Superset: coincide" in ev.estado_verificacion(path)
    text = path.read_text(encoding="utf-8")
    assert f"{len(ev.CATALOGO)} de {len(ev.CATALOGO)} charts devolvieron" in text and "pendiente" not in text


def test_running_the_same_month_again_creates_and_changes_nothing(settings, superset):
    _report(settings, superset)
    respaldo.build(settings, FEB)
    before = {kind: sorted(items) for kind, items in superset.objects.items()}
    superset.calls.clear()

    summary = respaldo.build(settings, FEB)

    assert {kind: sorted(items) for kind, items in superset.objects.items()} == before
    assert summary["escritos"] == {}
    assert superset.calls["POST chart"] == len(ev.CATALOGO) + len(ev.ANUALES)      # only chart/data queries: no chart created
    assert superset.calls["PUT chart"] == 0 and superset.calls["DELETE chart"] == 0


def test_each_dashboard_is_fixed_to_its_month_and_has_every_chart_in_its_tab(settings, superset):
    _report(settings, superset)
    respaldo.build(settings, FEB)
    dashboard = superset.dashboard("respaldo-local-2025-02")
    metadata, position = json.loads(dashboard["json_metadata"]), json.loads(dashboard["position_json"])
    mask = metadata["native_filter_configuration"][0]["defaultDataMask"]
    assert mask["extraFormData"]["filters"] == [{"col": "mes", "op": "IN", "val": ["2025-02"]}]
    for grafico in ev.CATALOGO:
        component = position[grafico.componente]                                   # the anchor of the links of the report
        assert component["parents"][:4] == ["ROOT_ID", "GRID_ID", "TABS-respaldo", f"TAB-{grafico.pestana}"]
        row = position[component["parents"][-1]]
        assert sum(position[c]["meta"]["width"] for c in row["children"]) <= 12
    year = json.loads(superset.dashboard("respaldo-local-2025")["json_metadata"])
    assert year["native_filter_configuration"][0]["defaultDataMask"]["extraFormData"]["filters"][0]["val"] == [2025]


def test_the_conclusions_of_the_report_are_next_to_their_charts(settings, superset):
    path = _report(settings, superset)
    respaldo.build(settings, FEB)
    position = json.loads(superset.dashboard("respaldo-local-2025-02")["position_json"])
    codes = [v["meta"]["code"] for v in position.values() if isinstance(v, dict) and v.get("type") == "MARKDOWN"]
    conclusions = ev.conclusiones_de(path)
    assert [group for group, _ in conclusions] == ["C1", "C2", "C3", "C4", "C5"]
    for group, text in conclusions:
        assert any(code == f"**Conclusión {group[1:]}.** {text}" for code in codes), group


def test_the_year_dashboard_names_the_twelve_months_and_what_is_missing(settings, superset):
    _report(settings, superset)
    respaldo.build(settings, FEB)
    position = json.loads(superset.dashboard("respaldo-local-2025")["position_json"])
    header = next(v["meta"]["code"] for v in position.values() if isinstance(v, dict) and v.get("type") == "MARKDOWN")
    rows = [line for line in header.splitlines() if re.match(r"\| [a-z]+&nbsp;.* 2025-", line)]
    assert len(rows) == 12
    assert "respaldo-local-2025-02" in rows[1] and "al día" in rows[1] and "+20,0 %" in rows[1]
    assert "sin datos" in rows[2] and "make all MES=2025-03" in rows[2]


def test_a_difference_is_reported_in_the_run_and_in_the_report(settings, superset):
    path = _report(settings, superset)
    respaldo.build(settings, FEB)
    superset.lie = {"viajes_por_dia_mes": 1.0}                                     # Superset shows something else

    summary = respaldo.build(settings, FEB)

    assert not summary["ok"]
    assert any(d.startswith("E6.2: ") for d in summary["diferencias"])
    assert "Verificación contra Superset: NO coincide" in ev.estado_verificacion(path)
    assert "- Diferencia: E6.2: " in path.read_text(encoding="utf-8")


def test_a_chart_removed_from_the_dashboard_is_a_difference(settings, superset):
    _report(settings, superset)
    respaldo.build(settings, FEB)
    dashboard = superset.dashboard("respaldo-local-2025-02")
    chart = next(i for i, c in superset.objects["chart"].items() if c["slice_name"].startswith("E1.1 "))
    superset.links[dashboard["id"]].discard(chart)
    problems = respaldo.verificar(settings, 2025)
    assert problems == ["respaldo-local-2025-02: E1.1: el chart no está en el tablero"]


def test_a_report_that_no_longer_matches_the_data_is_flagged(settings, superset):
    path = _report(settings, superset)
    respaldo.build(settings, FEB)
    path.write_text(path.read_text(encoding="utf-8").replace("2.400 viajes válidos", "2.399 viajes válidos"), encoding="utf-8")
    problems = respaldo.verificar(settings, 2025)
    assert len(problems) == 1 and "no están en sus charts" in problems[0]
    assert "NO coincide" in ev.estado_verificacion(path)


def test_a_month_without_comparison_gets_no_dashboard(settings, superset):
    summary = respaldo.build(settings, Month(2025, 3))
    assert not summary["mes_comparable"] and summary["ok"]
    assert "respaldo-local-2025-03" not in _slugs(superset)


def test_local_and_cloud_dashboards_live_side_by_side(settings, superset, monkeypatch):
    _report(settings, superset)
    respaldo.build(settings, FEB)
    local = {i: dict(c) for i, c in superset.objects["chart"].items()}
    cloud = replace(settings, warehouse="snowflake", ingest_mode="hybrid")
    superset.upper = True                                                          # Snowflake's column names
    con = duckdb.connect(str(settings.warehouse_db), read_only=True)

    def query(_settings, sql, _connection):
        cursor = con.execute(sql)
        return [d[0] for d in cursor.description], cursor.fetchall()

    class Open:
        def close(self):
            pass

    monkeypatch.setattr(resultados, "open_connection", lambda s: Open())
    monkeypatch.setattr(resultados, "run_query", query)

    summary = respaldo.build(cloud, FEB)
    con.close()

    assert summary["ok"], summary["diferencias"]
    assert _slugs(superset) == ["respaldo-local-2025", "respaldo-local-2025-02", "respaldo-nube-2025", "respaldo-nube-2025-02"]
    assert {i: superset.objects["chart"][i] for i in local} == local               # the local charts were not touched
    table = next(c for c in superset.objects["chart"].values() if c["slice_name"] == "E1.1 · Top 10 de zonas de pickup del mes [nube]")
    params = json.loads(table["params"])
    assert params["all_columns"][0] == "PUESTO_MES" and params["conditional_formatting"][0]["column"].isupper()
    mask = json.loads(superset.dashboard("respaldo-nube-2025-02")["json_metadata"])["native_filter_configuration"][0]["defaultDataMask"]
    assert mask["extraFormData"]["filters"][0]["col"] == "MES"
    # the report in results/ is the local one: the cloud run does not sign its verification, but its figures are the ones
    # of the cloud too, so the cloud dashboard shows its conclusions and says where it was written
    assert "respaldo-nube" not in resultados.results_file(FEB).read_text(encoding="utf-8")
    texts = _markdown(superset, "respaldo-nube-2025-02")
    assert any("se escribió en modo local" in t for t in texts)
    assert any(t.startswith("**Conclusión 1.** La demanda") for t in texts)
    assert "escrito en modo local" in _markdown(superset, "respaldo-nube-2025")[0]


def test_conclusions_that_are_not_those_of_the_data_are_not_shown(settings, superset):
    path = _report(settings, superset)
    path.write_text(path.read_text(encoding="utf-8").replace("+20,0 % de viajes", "+21,0 % de viajes"), encoding="utf-8")
    respaldo.build(settings, FEB)
    texts = _markdown(superset, "respaldo-local-2025-02")
    assert any("todavía no se generó con estos datos" in t for t in texts)
    assert not any("La demanda de taxis amarillos" in t for t in texts)
    assert "desactualizado" in _markdown(superset, "respaldo-local-2025")[0]


def test_charts_made_by_hand_and_the_other_dashboards_are_left_alone(settings, superset):
    superset.objects["chart"][900] = {"id": 900, "slice_name": "Mi chart", "params": "{}"}
    superset.objects["chart"][901] = {"id": 901, "slice_name": "E9.9 · Código que ya no existe [local]", "params": "{}"}
    superset.objects["dashboard"][902] = {"id": 902, "slug": "nyc-taxi-overview"}
    superset.next_id = 1000
    respaldo.build(settings, FEB)
    assert 900 in superset.objects["chart"] and 901 not in superset.objects["chart"]   # only an old evidence chart is removed
    assert 902 in superset.objects["dashboard"]


# --- Superset off ----------------------------------------------------------------------------------------------------
def test_with_superset_off_the_report_says_it_was_not_compared(settings, superset):
    path = _report(settings, superset)
    text = path.read_text(encoding="utf-8")
    assert "**Verificación contra Superset:** pendiente" in text
    assert "`make superset-dashboards MES=2025-02 INGEST_MODE=direct WAREHOUSE=duckdb`" in text


def test_the_commands_explain_that_superset_is_off(monkeypatch, capsys):
    monkeypatch.setenv("WAREHOUSE", "duckdb")
    monkeypatch.setattr(respaldo, "superset_expected", lambda: False)
    assert respaldo.main(["--mes", "2025-02", "--verificar"]) == 1
    assert "docker compose up -d" in capsys.readouterr().err


def test_the_verification_is_a_blocking_check_of_the_run():
    checks = {spec.name: spec for spec in orchestration.superset_respaldo.check_specs}
    assert checks["superset_coincide"].blocking
    assert {spec.name for spec in orchestration.resultados_md.check_specs} == {"cifras_respaldadas"}
