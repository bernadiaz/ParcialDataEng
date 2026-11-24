"""Tableros de respaldo en Superset: el que sustenta cada results/YYYY/RESULTS_MM.md y el de los 12 meses del año.

`make all` lo corre como último asset de Dagster (`superset_respaldo`) cuando el stack de docker compose está arriba, y
`make superset-dashboards` lo corre solo. Para el año de MES crea o actualiza:

  respaldo-<motor>-YYYY-MM   un tablero por cada mes del año que se puede comparar con el mismo mes del año anterior.
                             Una pestaña por sección del reporte; cada conclusión, al lado de los charts que la sustentan.
  respaldo-<motor>-YYYY      los 12 meses del año contra los 12 del año anterior, con la cobertura (qué falta cargar) y el
                             estado de cada reporte.

<motor> es "local" (copia DuckDB) o "nube" (Snowflake): un reporte y su tablero siempre leen el mismo warehouse, y una
corrida en un modo no toca el respaldo del otro. Los charts son compartidos: hay uno por código (E1.1, C2.1...), y cada
tablero lo filtra por su mes. Volver a correr un mes actualiza los mismos objetos, no crea otros.

Después compara: toma los charts y el filtro tal como quedaron guardados en Superset, pide sus datos por la API y los
contrasta, celda por celda, con la evidencia que usó el reporte; también vuelve a auditar el .md contra esos datos. El
resultado queda escrito en el propio .md (bloque VERIFICACION). Si algo no coincide, el paso falla.

    python -m src.respaldo --mes 2025-01              # crea, actualiza y verifica
    python -m src.respaldo --mes 2025-01 --verificar  # solo verifica los tableros y los reportes del año
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import evidencia as ev
from src import resultados
from src.config import RUN_ID, Month, Settings, get_logger
from src.dashboards import (
    ASSIGNED_COLOR,
    COMPARISON_COLOR,
    SupersetAPI,
    database_payload,
    match_columns,
    metric,
    superset_expected,
    superset_public_url,
    superset_url,
    where,
)
from src.evidencia import ANTERIOR, MES, Evidencia, Grafico
from src.interpretacion import MESES, entero, mes_es, signo

log = get_logger("respaldo")
SUBE, BAJA = "#ACE1C4", "#EFA1AA"  # condicionales de las columnas de variación (verde y rojo claros de Superset)
NOMBRE_CHART = re.compile(r"^(?P<codigo>[A-Z]\w*(?:\.\d+)?) · .* \[(?P<motor>local|nube)\]$")


class RespaldoError(RuntimeError):
    """Superset no muestra lo que dice el reporte."""


# --- datasets y charts --------------------------------------------------------------------------------------------
def nombre_dataset(tabla: str, motor: str) -> str:
    return f"respaldo_{tabla}_{motor}"


def nombre_chart(grafico: Grafico, motor: str) -> str:
    return f"{grafico.nombre} [{motor}]"


def parametros(grafico: Grafico) -> dict[str, Any]:
    """form_data de Superset para un chart del catálogo (nombres de columna en minúscula: match_columns los ajusta)."""
    formatos = dict(grafico.formatos)
    filtros = [where(ev.filtro_sql(grafico.filtro))] if grafico.filtro else []
    if grafico.tipo == "tabla":
        largo = grafico.codigo in {"E1.8", "A15"}
        # Solo porcentajes: en "variacion" se mezclan unidades (viajes, USD, puntos) y el color no diría nada.
        variaciones = [c for c in grafico.columnas if (c.startswith("variacion") and c.endswith("_pct")) or c == "cambio_pp"]
        return {
            "viz_type": "table", "query_mode": "raw", "all_columns": list(grafico.columnas), "adhoc_filters": filtros,
            "order_by_cols": [json.dumps([c, asc]) for c, asc in grafico.orden], "row_limit": 10000, "page_length": 50 if largo else 0,
            "include_search": largo, "show_cell_bars": False, "table_timestamp_format": "smart_date",
            "column_config": {c: {"d3NumberFormat": f} for c, f in formatos.items() if c in grafico.columnas},
            "conditional_formatting": [
                {"column": c, "operator": operador, "targetValue": 0, "colorScheme": color}
                for c in variaciones for operador, color in ((">", SUBE), ("<", BAJA))],
        }
    if grafico.tipo == "kpi":
        etiqueta, columna = grafico.metricas[0]
        return {"viz_type": "big_number_total", "metric": metric(f"MAX({columna})", etiqueta), "adhoc_filters": filtros,
                "subheader": "", "y_axis_format": formatos.get("y", "SMART_NUMBER"), "header_font_size": 0.3, "subheader_font_size": 0.125}
    linea = grafico.tipo == "lineas"
    params: dict[str, Any] = {
        "viz_type": "echarts_timeseries_line" if linea else "echarts_timeseries_bar", "x_axis": grafico.x,
        "metrics": [metric(f"MAX({columna})", etiqueta) for etiqueta, columna in grafico.metricas],
        "groupby": [grafico.serie] if grafico.serie else [], "adhoc_filters": filtros, "row_limit": 10000, "truncate_metric": True,
        "show_legend": True, "legendType": "scroll", "legendOrientation": "top", "rich_tooltip": True, "tooltipTimeFormat": "smart_date",
        "x_axis_title": grafico.eje_x, "x_axis_title_margin": 30, "y_axis_title": grafico.eje_y, "y_axis_title_margin": 50,
        "y_axis_title_position": "Left", "y_axis_format": formatos.get("y", "SMART_NUMBER"), "xAxisForceCategorical": True,
        "color_scheme": "supersetColors", "markerEnabled": linea, "x_axis_sort_asc": True, "show_value": grafico.valores,
        # Primero el mes del reporte: "Mes..." antes que "Mismo mes..." y, con un período por serie, 2025-01 antes que 2024-01.
        "sort_series_type": "name", "sort_series_ascending": not grafico.serie,
    }
    if grafico.horizontal:
        params |= {"orientation": "horizontal", "x_axis_title": "", "y_axis_title": ""}
    if grafico.orden and grafico.orden[0][0].startswith("puesto"):  # zonas: de mayor a menor, no alfabético
        ascendente = grafico.horizontal  # a lo ancho, Superset dibuja la primera barra abajo: así la mayor queda arriba
        if len(grafico.metricas) == 1:
            params |= {"x_axis_sort": grafico.metricas[0][0], "x_axis_sort_asc": ascendente}
        else:  # con dos series Superset ordena por el total de las dos
            params |= {"x_axis_sort_series": "sum", "x_axis_sort_series_ascending": ascendente}
    return params


def ajustar(params: dict[str, Any], columnas: dict[str, str]) -> dict[str, Any]:
    """match_columns más las columnas del formato condicional (Snowflake devuelve los nombres en mayúscula)."""
    out = match_columns(params, columnas)
    if out.get("conditional_formatting"):
        out["conditional_formatting"] = [{**c, "column": columnas.get(c["column"].lower(), c["column"])} for c in out["conditional_formatting"]]
    return out


# --- tableros -------------------------------------------------------------------------------------------------------
def filas_de(graficos: list[Grafico]) -> list[list[Grafico]]:
    """Acomoda los charts de una pestaña en filas de 12 columnas, en el orden del catálogo."""
    filas: list[list[Grafico]] = []
    for grafico in graficos:
        if not filas or sum(g.ancho for g in filas[-1]) + grafico.ancho > 12:
            filas.append([])
        filas[-1].append(grafico)
    return filas


class Posicion:
    """position_json de un tablero: encabezado, pestañas y filas."""

    def __init__(self, titulo: str):
        self.pos: dict[str, Any] = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
            "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": titulo}},
        }
        self.n = 0

    def _nuevo(self, tipo: str, padre: str, meta: dict[str, Any], id_: str = "") -> str:
        self.n += 1
        id_ = id_ or f"{tipo}-{self.n}"
        self.pos[id_] = {"type": tipo, "id": id_, "children": [], "parents": [*self.pos[padre].get("parents", []), padre], "meta": meta}
        self.pos[padre]["children"].append(id_)
        return id_

    def fila(self, padre: str = "GRID_ID") -> str:
        return self._nuevo("ROW", padre, {"background": "BACKGROUND_TRANSPARENT"})

    def texto(self, padre: str, codigo: str, alto: int, ancho: int = 12) -> None:
        self._nuevo("MARKDOWN", self.fila(padre), {"width": ancho, "height": alto, "code": codigo})

    def pestanas(self) -> str:
        return self._nuevo("TABS", "GRID_ID", {}, "TABS-respaldo")

    def pestana(self, clave: str, titulo: str) -> str:
        return self._nuevo("TAB", "TABS-respaldo", {"text": titulo, "defaultText": titulo, "placeholder": titulo}, f"TAB-{clave}")

    def charts(self, padre: str, graficos: list[Grafico], ids: dict[str, int]) -> None:
        for fila in filas_de(graficos):
            row = self.fila(padre)
            for g in fila:
                self._nuevo("CHART", row, {"chartId": ids[g.codigo], "width": g.ancho, "height": g.alto, "sliceName": g.nombre,
                                           "sliceNameOverride": g.nombre}, g.componente)


def filtro_nativo(nombre: str, columna: str, valor: Any, dataset_id: int, charts: list[int], pestanas: list[str]) -> dict[str, Any]:
    """Filtro del tablero con su valor fijado: el mes (o el año) que el tablero respalda."""
    return {
        "id": f"NATIVE_FILTER-{columna.lower()}", "name": nombre, "type": "NATIVE_FILTER", "filterType": "filter_select",
        "targets": [{"datasetId": dataset_id, "column": {"name": columna}}],
        "controlValues": {"enableEmptyFilter": True, "defaultToFirstItem": False, "multiSelect": False, "searchAllOptions": False,
                          "inverseSelection": False},
        "defaultDataMask": {"extraFormData": {"filters": [{"col": columna, "op": "IN", "val": [valor]}]},
                            "filterState": {"value": [valor], "label": str(valor)}, "ownState": {}},
        "cascadeParentIds": [], "scope": {"rootPath": ["ROOT_ID"], "excluded": []}, "chartsInScope": charts, "tabsInScope": pestanas,
        "description": "Fijado por el tablero: cada reporte tiene el suyo",
    }


def encabezado_mes(settings: Settings, mes: Month, evidencia: Evidencia, reporte: Path) -> str:
    viajes, recaudacion = evidencia.indicador("viajes"), evidencia.indicador("recaudacion")
    anio = ev.slug_anio(settings, mes.year)
    estado = (f"Sustenta `results/{mes.year}/{reporte.name}`" if resultados.has_figures(reporte) and ev.motor_de(reporte) == ev.motor(settings)
              else f"El reporte `results/{mes.year}/{reporte.name}` de este modo todavía no se generó (`make all {ev.argumentos_make(settings, mes)}`)")
    return (
        f"### {mes_es(mes).capitalize()} contra {mes_es(mes.comparison)}: {signo(viajes['variacion_pct'])} de viajes, "
        f"{signo(recaudacion['variacion_pct'])} de recaudación\n"
        f"{estado}. Cada chart tiene el código que cita el reporte (E1.1, C2.1...) y lee la misma tabla `marts.ev_*` que el reporte, en "
        f"{'la copia local de DuckDB' if ev.motor(settings) == 'local' else 'Snowflake'}. "
        f"Los 12 meses de {mes.year}: [{anio}](/superset/dashboard/{anio}/).")


def tablero_mes(settings: Settings, mes: Month, evidencia: Evidencia, ids: dict[str, int]) -> dict[str, Any]:
    reporte = resultados.results_file(mes)
    titulo = f"Taxi NYC | Respaldo {mes_es(mes)} vs {mes_es(mes.comparison)} ({ev.motor(settings)})"
    p = Posicion(titulo)
    p.texto("GRID_ID", encabezado_mes(settings, mes, evidencia, reporte), 17)
    p.pestanas()
    propias = ev.conclusiones_de(reporte) if resultados.has_figures(reporte) and ev.motor_de(reporte) == ev.motor(settings) else []
    for clave, nombre in ev.PESTANAS:
        tab = p.pestana(clave, nombre)
        graficos = [g for g in ev.CATALOGO if g.pestana == clave]
        if clave != "conclusiones":
            p.charts(tab, graficos, ids)
            continue
        for grupo in dict.fromkeys(g.codigo.split(".")[0] for g in graficos):
            texto = next((t for codigo, t in propias if codigo == grupo), None)
            if texto is None:
                texto = ("_El reporte de este mes no tiene esta conclusión._" if propias else
                         "_La conclusión aparece acá cuando se genera el reporte de este mes._")
            p.texto(tab, f"**Conclusión {grupo[1:]}.** {texto}", 7 + 3 * (len(texto) // 150 + 1))
            p.charts(tab, [g for g in graficos if g.codigo.split(".")[0] == grupo], ids)
    return {"slug": ev.slug_mes(settings, mes), "titulo": titulo, "posicion": p.pos, "colores": {mes.label: ASSIGNED_COLOR,
            mes.comparison.label: COMPARISON_COLOR}, "filtro": ("Mes del reporte", "mes", mes.label), "graficos": ev.CATALOGO}


@dataclass
class EstadoReporte:
    """Qué dice results/YYYY/RESULTS_MM.md de un mes, comparado con la evidencia de ahora."""

    mes: Month
    existe: bool = False
    motor: str | None = None
    cifras: int = 0
    sin_respaldo: int = 0

    def texto(self, motor: str) -> str:
        if not self.existe:
            return "sin generar"
        if self.motor != motor:
            return f"generado en modo {self.motor or 'anterior a los tableros de respaldo'}"
        if self.sin_respaldo:
            return f"desactualizado ({self.sin_respaldo} de {self.cifras} cifras cambiaron): volver a correr el mes"
        return f"al día ({self.cifras} cifras, todas en el tablero)"


def estado_reporte(mes: Month, evidencia: Evidencia | None) -> EstadoReporte:
    path = resultados.results_file(mes)
    if not resultados.has_figures(path):
        return EstadoReporte(mes)
    cifras = ev.auditar(path.read_text(encoding="utf-8"), evidencia) if evidencia is not None and evidencia.existe else []
    return EstadoReporte(mes, True, ev.motor_de(path), len(cifras), sum(not c.respaldada for c in cifras))


def encabezado_anio(settings: Settings, anio: int, completo: Evidencia, por_mes: dict[str, Evidencia]) -> str:
    """Los 12 meses del año: tablero, reporte, variación y estado. Un mes sin datos se dice, nunca se completa."""
    motor, hoy = ev.motor(settings), datetime.now(timezone.utc)
    cobertura = {str(r["mes"]): r for r in completo.tablas.get("ev_cobertura", [])}

    def fila(*celdas: str) -> str:  # las tablas de Markdown de Superset no separan sus columnas: se separan con espacios
        return "| " + " | ".join(f"{celda}&nbsp;&nbsp;&nbsp;" for celda in celdas) + " |"

    lineas = [f"### Los 12 meses de {anio} contra los mismos meses de {anio - 1}",
              f"Cada fila es una comparación con su tablero y su reporte (`results/{anio}/RESULTS_MM.md`). Se muestran los datos cargados en "
              f"{'la copia local de DuckDB' if motor == 'local' else 'Snowflake'}; un mes que falta no se estima.", "",
              fila("mes", "comparación", "viajes", "recaudación", "tablero", "reporte"), "|---|---|---:|---:|---|---|"]
    for numero in range(1, 13):
        mes = Month(anio, numero)
        evidencia = por_mes.get(mes.label)
        if evidencia is not None and evidencia.existe:
            slug = ev.slug_mes(settings, mes)
            lineas.append(fila(MESES[numero - 1], f"{mes} vs {mes.comparison}", signo(evidencia.indicador("viajes")["variacion_pct"]),
                               signo(evidencia.indicador("recaudacion")["variacion_pct"]), f"[{slug}](/superset/dashboard/{slug}/)",
                               f"`RESULTS_{numero:02d}.md`: {estado_reporte(mes, evidencia).texto(motor)}"))
            continue
        if (anio, numero) > (hoy.year, hoy.month):
            motivo = "mes futuro"
        else:
            estado = str(cobertura.get(mes.label, {}).get("estado") or "mes sin cargar")
            motivo = f"{estado} (`make all {ev.argumentos_make(settings, mes)}`)"
        lineas.append(fila(MESES[numero - 1], f"{mes} vs {mes.comparison}", "sin datos", "sin datos", "-", motivo))
    return "\n".join(lineas)


def tablero_anio(settings: Settings, anio: int, completo: Evidencia, por_mes: dict[str, Evidencia], ids: dict[str, int]) -> dict[str, Any]:
    titulo = f"Taxi NYC | Los 12 meses de {anio} vs {anio - 1} ({ev.motor(settings)})"
    p = Posicion(titulo)
    p.texto("GRID_ID", encabezado_anio(settings, anio, completo, por_mes), 54)
    p.pestanas()
    for clave, nombre in ev.PESTANAS_ANUALES:
        p.charts(p.pestana(clave, nombre), [g for g in ev.ANUALES if g.pestana == clave], ids)
    return {"slug": ev.slug_anio(settings, anio), "titulo": titulo, "posicion": p.pos, "colores": {},
            "filtro": ("Año del reporte", "anio", anio), "graficos": ev.ANUALES}


# --- aprovisionamiento --------------------------------------------------------------------------------------------
class Aprovisionador:
    """Crea o actualiza conexión, datasets, charts y tableros. Lee una vez lo que ya existe y solo escribe lo que cambió."""

    def __init__(self, api: SupersetAPI, settings: Settings):
        self.api, self.settings, self.motor = api, settings, ev.motor(settings)
        self.datasets: dict[str, int] = {}
        self.columnas: dict[str, dict[str, str]] = {}
        self.charts: dict[str, int] = {}
        self.escritos = Counter()

    def conexion(self, mes: Month, exportar: bool) -> tuple[int, str]:
        payload, esquema = database_payload(self.settings, mes, export=exportar)
        return self.api.upsert("database", "database_name", payload), esquema

    def crear_datasets(self, db_id: int, esquema: str) -> None:
        existentes = {d["table_name"]: d["id"] for d in self.api.list_all("dataset")}
        for tabla in ev.TABLAS:
            nombre, sql = nombre_dataset(tabla, self.motor), f"select * from marts.{tabla}"
            if nombre in existentes:
                self.datasets[tabla] = existentes[nombre]
                self.api._ok(self.api.http.put(f"/api/v1/dataset/{existentes[nombre]}",
                                               json={"sql": sql, "database_id": db_id, "schema": esquema}))
            else:
                self.datasets[tabla] = self.api._ok(self.api.http.post("/api/v1/dataset/", json={
                    "database": db_id, "schema": esquema, "table_name": nombre, "sql": sql}))["id"]
                self.escritos["datasets nuevos"] += 1
            self.api.refresh_dataset(self.datasets[tabla])
            self.columnas[tabla] = self.api.dataset_columns(self.datasets[tabla])

    def crear_charts(self) -> None:
        existentes: dict[str, dict[str, Any]] = {}
        sobrantes: list[int] = []
        for chart in self.api.list_all("chart"):
            m = NOMBRE_CHART.match(chart.get("slice_name") or "")
            if m is None or m["motor"] != self.motor:
                continue
            if m["codigo"] in ev.POR_CODIGO and m["codigo"] not in existentes:
                existentes[m["codigo"]] = chart
            else:  # un código que ya no está en el catálogo, o una copia repetida
                sobrantes.append(chart["id"])
        for grafico in (*ev.CATALOGO, *ev.ANUALES):
            params = ajustar(parametros(grafico), self.columnas[grafico.tabla]) | {"datasource": f"{self.datasets[grafico.tabla]}__table"}
            payload = {"slice_name": nombre_chart(grafico, self.motor), "viz_type": params["viz_type"],
                       "datasource_id": self.datasets[grafico.tabla], "datasource_type": "table", "params": json.dumps(params),
                       "description": f"{grafico.muestra.capitalize()}. Tabla marts.{grafico.tabla}."}
            actual = existentes.get(grafico.codigo)
            if actual is None:
                self.charts[grafico.codigo] = self.api._ok(self.api.http.post("/api/v1/chart/", json=payload))["id"]
                self.escritos["charts nuevos"] += 1
                continue
            self.charts[grafico.codigo] = actual["id"]
            iguales = all(actual.get(k) == payload[k] for k in ("slice_name", "viz_type", "datasource_id", "description"))
            if not iguales or json.loads(actual.get("params") or "{}") != params:
                # La consulta que Superset guardó al abrir el chart queda vieja: se borra y la rearma desde params.
                self.api._ok(self.api.http.put(f"/api/v1/chart/{actual['id']}", json=payload | {"query_context": None}))
                self.escritos["charts actualizados"] += 1
        for chart_id in sobrantes:
            self.api._ok(self.api.http.delete(f"/api/v1/chart/{chart_id}"))
            self.escritos["charts borrados"] += 1

    def guardar_tablero(self, tablero: dict[str, Any]) -> dict[str, Any]:
        dash_id = self.api.dashboard_by_slug(tablero["slug"])
        if dash_id is None:
            dash_id = self.api._ok(self.api.http.post("/api/v1/dashboard/", json={
                "dashboard_title": tablero["titulo"], "slug": tablero["slug"], "published": True}))["id"]
            self.escritos["tableros nuevos"] += 1
        nombre, columna, valor = tablero["filtro"]
        tabla = "ev_indicadores"
        real = self.columnas[tabla].get(columna, columna)
        charts = [self.charts[g.codigo] for g in tablero["graficos"]]
        pestanas = [k for k, v in tablero["posicion"].items() if isinstance(v, dict) and v.get("type") == "TAB"]
        metadata = {
            "positions": tablero["posicion"],  # Superset relaciona los charts del tablero a partir de las posiciones
            "native_filter_configuration": [filtro_nativo(nombre, real, valor, self.datasets[tabla], charts, pestanas)],
            "label_colors": {MES: ASSIGNED_COLOR, ANTERIOR: COMPARISON_COLOR, **tablero["colores"]},
            "color_scheme": "supersetColors", "refresh_frequency": 0, "timed_refresh_immune_slices": [], "expanded_slices": {},
            "cross_filters_enabled": False, "filter_bar_orientation": "HORIZONTAL",
        }
        self.api._ok(self.api.http.put(f"/api/v1/dashboard/{dash_id}", json={
            "dashboard_title": tablero["titulo"], "published": True, "json_metadata": json.dumps(metadata)}))
        return {"title": tablero["titulo"], "slug": tablero["slug"], "charts": len(charts),
                "url": ev.url_tablero(superset_public_url(), tablero["slug"])}


# --- verificación: lo que Superset muestra contra lo que dice el reporte -------------------------------------------------
@dataclass
class Verificacion:
    """Resultado de comparar un tablero guardado en Superset con la evidencia."""

    slug: str
    charts: int = 0
    iguales: int = 0
    celdas: int = 0
    diferencias: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diferencias and self.charts == self.iguales


def canonica(valor: Any) -> Any:
    """Un valor comparable entre motores: números con 10 cifras significativas, el resto como texto."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return None
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float)):
        return format(float(valor), ".10g")
    return str(valor)


def consulta_guardada(form: dict[str, Any], filtros: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """La consulta de un chart, armada con sus parámetros guardados y el filtro guardado del tablero. Devuelve también los
    nombres de las columnas del resultado, en el orden de Grafico.columnas_datos."""
    condiciones = [f["sqlExpression"] for f in form.get("adhoc_filters") or [] if f.get("expressionType") == "SQL"]
    consulta: dict[str, Any] = {
        "filters": filtros, "extras": {"where": " AND ".join(f"({c})" for c in condiciones), "having": ""}, "row_limit": 10000,
        "orderby": [], "annotation_layers": [], "applied_time_extras": {}, "url_params": {}, "custom_params": {},
        "custom_form_data": {}, "time_range": "No filter"}
    if form["viz_type"] == "table":
        columnas = list(form["all_columns"])  # sin "metrics": filas tal cual, sin GROUP BY (como la tabla en modo raw)
        consulta |= {"columns": columnas, "orderby": [json.loads(o) for o in form.get("order_by_cols") or []]}
        return consulta, columnas
    if form["viz_type"] == "big_number_total":
        consulta |= {"columns": [], "metrics": [form["metric"]]}
        return consulta, [form["metric"]["label"]]
    columnas = [form["x_axis"], *(form.get("groupby") or [])]
    consulta |= {"columns": columnas, "metrics": form["metrics"]}
    return consulta, [*columnas, *(m["label"] for m in form["metrics"])]


def datos_guardados(api: SupersetAPI, form: dict[str, Any], filtros: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    consulta, nombres = consulta_guardada(form, filtros)
    dataset_id = int(str(form["datasource"]).split("__")[0])
    body = api._ok(api.http.post("/api/v1/chart/data", json={
        "datasource": {"id": dataset_id, "type": "table"}, "force": True, "queries": [consulta], "result_format": "json", "result_type": "full"}))
    resultado = body["result"][0]
    if resultado.get("error"):
        raise RespaldoError(f"Superset no pudo consultar un chart: {resultado['error']}")
    filas = [{str(k).lower(): v for k, v in fila.items()} for fila in resultado["data"]]
    return [tuple(canonica(fila.get(n.lower())) for n in nombres) for fila in filas]


def esperados(grafico: Grafico, evidencia: Evidencia) -> list[tuple[Any, ...]]:
    """Las filas que el chart tiene que mostrar, según la evidencia que usa el reporte."""
    filas = grafico.filas(evidencia)
    if grafico.tipo == "tabla":
        columnas = list(grafico.columnas)
    else:
        columnas = ([grafico.x] if grafico.x else []) + ([grafico.serie] if grafico.serie else []) + [c for _, c in grafico.metricas]
        if grafico.tipo == "kpi" and not filas:
            return [(None,)]
    return [tuple(canonica(r[c]) for c in columnas) for r in filas]


def verificar_tablero(api: SupersetAPI, slug: str, graficos: tuple[Grafico, ...], evidencia: Evidencia, motor: str) -> Verificacion:
    """Toma el tablero tal como está guardado en Superset y compara los datos de cada chart con la evidencia."""
    v = Verificacion(slug, charts=len(graficos))
    respuesta = api.http.get(f"/api/v1/dashboard/{slug}")
    if respuesta.status_code == 404:
        v.diferencias.append(f"el tablero {slug} no existe")
        return v
    tablero = api._ok(respuesta)["result"]
    posicion = json.loads(tablero.get("position_json") or "{}")
    metadata = json.loads(tablero.get("json_metadata") or "{}")
    filtros = [f for config in metadata.get("native_filter_configuration", [])
               for f in config["defaultDataMask"]["extraFormData"]["filters"]]
    guardados: dict[str, dict[str, Any]] = {}
    for chart in api._ok(api.http.get(f"/api/v1/dashboard/{slug}/charts"))["result"]:
        m = NOMBRE_CHART.match(chart.get("slice_name") or "")
        if m is not None and m["motor"] == motor:
            guardados[m["codigo"]] = chart
    for grafico in graficos:
        chart = guardados.get(grafico.codigo)
        if chart is None or grafico.componente not in posicion:
            v.diferencias.append(f"{grafico.codigo}: el chart no está en el tablero")
            continue
        datos, esperado = datos_guardados(api, chart["form_data"], filtros), esperados(grafico, evidencia)
        v.celdas += sum(len(fila) for fila in esperado)
        if Counter(datos) == Counter(esperado):
            v.iguales += 1
            continue
        faltan, sobran = list((Counter(esperado) - Counter(datos)).elements()), list((Counter(datos) - Counter(esperado)).elements())
        v.diferencias.append(f"{grafico.codigo}: {len(faltan)} filas de la evidencia no están en Superset y {len(sobran)} de Superset no están en "
                             f"la evidencia (por ejemplo {(faltan or sobran)[0]})")
    return v


def texto_verificacion(mes: Month, mensual: Verificacion, anual: Verificacion, reporte: EstadoReporte) -> str:
    ahora = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, corrida `{RUN_ID}`"
    ok = mensual.ok and anual.ok and not reporte.sin_respaldo
    lineas = [f"**Verificación contra Superset:** {'coincide' if ok else 'NO coincide'} ({ahora}).", "",
              f"- Tablero `{mensual.slug}`: {mensual.iguales} de {mensual.charts} charts devolvieron por la API exactamente los datos de este reporte "
              f"({entero(mensual.celdas)} celdas comparadas).",
              f"- Tablero `{anual.slug}`: {anual.iguales} de {anual.charts} charts ({entero(anual.celdas)} celdas).",
              f"- Números de este reporte: {reporte.cifras - reporte.sin_respaldo} de {reporte.cifras} se ven en los charts que cita su bloque."]
    lineas += [f"- Diferencia: {d}" for d in (*mensual.diferencias, *anual.diferencias)]
    return "\n".join(lineas)


def escribir_verificacion(path: Path, contenido: str) -> bool:
    if not path.exists():
        return False
    texto = ev.reemplazar_verificacion(path.read_text(encoding="utf-8"), contenido)
    if texto is None:
        return False
    path.write_text(texto, encoding="utf-8")
    return True


# --- pasos ------------------------------------------------------------------------------------------------------------
def conectar_superset() -> SupersetAPI:
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("SUPERSET_ADMIN_PASSWORD is empty: set it in .env (the same value docker compose uses)")
    return SupersetAPI(superset_url(), os.environ.get("SUPERSET_ADMIN_USER", "admin").strip() or "admin", password)


def leer_warehouse(settings: Settings, anio: int) -> tuple[Evidencia, dict[str, Evidencia]]:
    conexion = resultados.open_connection(settings)
    try:
        return ev.leer_anio(lambda sql: resultados.run_query(settings, sql, conexion), anio)
    finally:
        conexion.close()


def build(settings: Settings, mes: Month, exportar: bool = True) -> dict[str, Any]:
    """Crea o actualiza los tableros del año de MES, verifica el del mes y el anual, y lo deja escrito en el .md."""
    completo, por_mes = leer_warehouse(settings, mes.year)
    api = conectar_superset()
    obra = Aprovisionador(api, settings)
    obra.crear_datasets(*obra.conexion(mes, exportar))
    obra.crear_charts()
    tableros = [obra.guardar_tablero(tablero_anio(settings, mes.year, completo, por_mes, obra.charts))]
    for etiqueta, evidencia in por_mes.items():
        if evidencia.existe:
            tableros.append(obra.guardar_tablero(tablero_mes(settings, Month.parse(etiqueta), evidencia, obra.charts)))
    log.info("respaldo %s: %d tableros, %d charts (%s)", ev.motor(settings), len(tableros), len(obra.charts),
             ", ".join(f"{n} {k}" for k, n in obra.escritos.items()) or "sin cambios en datasets y charts")

    anual = verificar_tablero(api, ev.slug_anio(settings, mes.year), ev.ANUALES, completo, obra.motor)
    evidencia = por_mes.get(mes.label)
    resumen = {"tableros": tableros, "charts": len(obra.charts), "escritos": dict(obra.escritos), "mes_comparable": False,
               "verificacion": f"anual {anual.iguales}/{anual.charts}", "ok": anual.ok, "diferencias": list(anual.diferencias)}
    if evidencia is None or not evidencia.existe:
        log.warning("%s no se puede comparar con lo cargado: su tablero no se crea y su reporte lo dice", mes)
        return resumen
    path = resultados.results_file(mes)
    mensual = verificar_tablero(api, ev.slug_mes(settings, mes), ev.CATALOGO, evidencia, obra.motor)
    reporte = estado_reporte(mes, evidencia)
    del_motor = reporte.existe and reporte.motor == obra.motor
    if del_motor:
        escribir_verificacion(path, texto_verificacion(mes, mensual, anual, reporte))
    diferencias = [*mensual.diferencias, *anual.diferencias]
    if del_motor and reporte.sin_respaldo:
        diferencias.append(f"{path.name}: {reporte.sin_respaldo} de {reporte.cifras} cifras no están en los charts que cita")
    log.info("verificación %s: %d/%d charts del mes (%d celdas), %d/%d del año, %d/%d cifras de %s", mes, mensual.iguales, mensual.charts,
             mensual.celdas, anual.iguales, anual.charts, reporte.cifras - reporte.sin_respaldo, reporte.cifras, path.name)
    resumen |= {"mes_comparable": True, "ok": not diferencias, "diferencias": diferencias, "reporte": str(path),
                "verificacion": f"mes {mensual.iguales}/{mensual.charts}, año {anual.iguales}/{anual.charts}, cifras del reporte "
                                f"{reporte.cifras - reporte.sin_respaldo}/{reporte.cifras}",
                "celdas": mensual.celdas + anual.celdas}
    return resumen


def verificar(settings: Settings, anio: int, solo: Month | None = None) -> list[str]:
    """Compara los tableros ya creados y los reportes ya escritos de un año (o de un mes) con el warehouse. Devuelve los
    problemas; no crea ni modifica nada, salvo el bloque de verificación de los reportes que se comprobaron."""
    completo, por_mes = leer_warehouse(settings, anio)
    api, motor, problemas = conectar_superset(), ev.motor(settings), []
    anual = verificar_tablero(api, ev.slug_anio(settings, anio), ev.ANUALES, completo, motor)
    print(f"{anual.slug}: {anual.iguales}/{anual.charts} charts, {anual.celdas} celdas")
    problemas += [f"{anual.slug}: {d}" for d in anual.diferencias]
    for etiqueta, evidencia in por_mes.items():
        mes = Month.parse(etiqueta)
        if not evidencia.existe or (solo is not None and mes != solo):
            continue
        v, reporte = verificar_tablero(api, ev.slug_mes(settings, mes), ev.CATALOGO, evidencia, motor), estado_reporte(mes, evidencia)
        print(f"{v.slug}: {v.iguales}/{v.charts} charts, {v.celdas} celdas; {resultados.results_file(mes).name}: {reporte.texto(motor)}")
        problemas += [f"{v.slug}: {d}" for d in v.diferencias]
        if reporte.existe and reporte.motor == motor:
            if reporte.sin_respaldo:
                problemas.append(f"{resultados.results_file(mes)}: {reporte.sin_respaldo} de {reporte.cifras} cifras no están en sus charts")
            escribir_verificacion(resultados.results_file(mes), texto_verificacion(mes, v, anual, reporte))
    return problemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mes", required=True, help="YYYY-MM: su año define los 12 meses")
    parser.add_argument("--verificar", action="store_true", help="no crea nada: compara lo que ya está en Superset y en results/")
    parser.add_argument("--solo-mes", action="store_true", help="con --verificar, solo el mes (por defecto, todo el año)")
    args = parser.parse_args(argv)
    settings, mes = Settings.from_env(), Month.parse(args.mes)
    if not superset_expected():
        print(f"Superset is not running ({superset_url()}): start the stack with `docker compose up -d`.", file=sys.stderr)
        return 1
    if args.verificar:
        problemas = verificar(settings, mes.year, mes if args.solo_mes else None)
    else:
        problemas = build(settings, mes)["diferencias"]
    for problema in problemas:
        print(f"DIFERENCIA  {problema}", file=sys.stderr)
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
