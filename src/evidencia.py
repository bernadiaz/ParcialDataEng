"""Respaldo de los reportes: qué chart de Superset sustenta cada cifra y cada conclusión de results/YYYY/RESULTS_MM.md.

Hay una sola fuente: los modelos dbt de evidencia (marts.ev_*, dbt_taxi/models/evidence). El reporte y Superset
leen esas mismas tablas, así que una cifra del .md y la de su chart son el mismo valor guardado. Este módulo tiene:

  CATALOGO / ANUALES   los charts: qué tabla y columnas muestra cada uno, con qué filtro y en qué pestaña.
                       src/respaldo.py los crea en Superset y src/resultados.py los cita en el .md.
  CITAS                qué charts respaldan cada bloque del reporte (tabla, interpretación, conclusión).
  leer                 las filas de evidencia de un mes, en DuckDB o en Snowflake.
  reconciliar          las respuestas de sql/q1..q6 contra la evidencia: si una no coincide, el reporte no se escribe.
  auditar              recorre el .md ya escrito y, para cada número, busca el valor en los charts que ese mismo
                       bloque cita. Un número que ningún chart citado muestra queda señalado como "sin respaldo".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

from src.config import Month, Settings, get_logger

log = get_logger("evidencia")

Query = Callable[[str], tuple[list[str], list[tuple]]]
Filtro = tuple[tuple[str, str, Any], ...]

# Etiquetas de las dos series de cada comparación (nombres de métrica en los charts).
MES, ANTERIOR = "Mes del reporte", "Mismo mes, año anterior"

ENTERO, DOS, UNO, USD, USD_M, PCT, PCT_SIGNO, SIGNO, LIBRE = (
    ",d", ",.2f", ",.1f", "$,.2f", "$,.3s", ",.2f", "+,.2f", "+,d", ",.2~f")


@dataclass(frozen=True)
class Grafico:
    """Un chart de Superset que respalda cifras del reporte. `codigo` es el que cita el .md."""

    codigo: str
    titulo: str
    tabla: str                                      # marts.<tabla>
    tipo: str                                       # tabla | kpi | barras | lineas
    pestana: str
    muestra: str                                    # qué cifras sustenta, en palabras
    columnas: tuple[str, ...] = ()                  # tipo tabla: columnas que se ven
    x: str = ""                                     # barras y líneas: eje X
    metricas: tuple[tuple[str, str], ...] = ()      # kpi, barras y líneas: (etiqueta, columna)
    serie: str = ""                                 # barras y líneas: una serie por valor de esta columna
    filtro: Filtro = ()
    orden: tuple[tuple[str, bool], ...] = ()        # (columna, ascendente)
    formatos: tuple[tuple[str, str], ...] = ()      # columna (o "y") -> formato d3
    ancho: int = 12
    alto: int = 40
    eje_x: str = ""
    eje_y: str = ""

    @property
    def nombre(self) -> str:
        return f"{self.codigo} · {self.titulo}"

    @property
    def componente(self) -> str:
        """Id del chart dentro del tablero: el ancla del enlace (#CHART-E1-1)."""
        return "CHART-" + self.codigo.replace(".", "-")

    @property
    def columnas_datos(self) -> tuple[str, ...]:
        """Columnas que el chart pide a la tabla, en orden y sin repetir."""
        if self.tipo == "tabla":
            return self.columnas
        propias = ((self.x,) if self.x else ()) + ((self.serie,) if self.serie else ())
        return tuple(dict.fromkeys(propias + tuple(c for _, c in self.metricas)))

    def filas(self, evidencia: "Evidencia") -> list[dict[str, Any]]:
        """Las filas que muestra el chart en el mes de la evidencia."""
        rows = [r for r in evidencia.tablas.get(self.tabla, []) if cumple(r, self.filtro)]
        for columna, ascendente in reversed(self.orden):
            rows.sort(key=lambda r, c=columna: (r[c] is None, r[c] if r[c] is not None else 0), reverse=not ascendente)
        return rows


def cumple(row: dict[str, Any], filtro: Filtro) -> bool:
    for columna, operador, valor in filtro:
        actual = row.get(columna)
        if actual is None:
            return False
        ok = {"=": lambda: actual == valor, "!=": lambda: actual != valor, "<=": lambda: actual <= valor,
              ">=": lambda: actual >= valor, "IN": lambda: actual in valor}[operador]()
        if not ok:
            return False
    return True


def filtro_sql(filtro: Filtro) -> str:
    """El mismo filtro, como SQL portable (identificadores sin comillas: valen en DuckDB y en Snowflake)."""
    def literal(valor: Any) -> str:
        return str(valor) if isinstance(valor, (int, float)) else "'" + str(valor).replace("'", "''") + "'"

    partes = []
    for columna, operador, valor in filtro:
        if operador == "IN":
            partes.append(f"{columna} IN ({', '.join(literal(v) for v in valor)})")
        else:
            partes.append(f"{columna} {operador} {literal(valor)}")
    return " AND ".join(partes)


def ind(*ids: str) -> Filtro:
    return (("indicador_id", "IN", ids),)


# --- catálogo: tablero mensual --------------------------------------------------------------------------------
PESTANAS: tuple[tuple[str, str], ...] = (
    ("resumen", "Resumen"),
    ("calidad", "Calidad y cuarentena"),
    ("zonas", "1 · Zonas"),
    ("horas", "2 · Horas"),
    ("peaje", "3 · Peaje CBD"),
    ("pagos", "4 · Pagos y propinas"),
    ("aeropuertos", "5 · Aeropuertos"),
    ("variacion", "6 · Variación interanual"),
    ("conclusiones", "Conclusiones"),
)

_IND = ("indicador", "unidad", "valor_mes", "valor_anterior", "variacion", "variacion_pct")
_IND_FMT = (("valor_mes", LIBRE), ("valor_anterior", LIBRE), ("variacion", LIBRE), ("variacion_pct", LIBRE))
_ZONAS = ("puesto_mes", "zona", "borough", "viajes_mes", "viajes_anterior", "variacion", "variacion_pct", "puesto_anterior")
_ZONAS_FMT = (("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("variacion", SIGNO), ("variacion_pct", PCT_SIGNO))
_DOS_MESES = ((MES, "viajes_mes"), (ANTERIOR, "viajes_anterior"))
_VALORES = ((MES, "valor_mes"), (ANTERIOR, "valor_anterior"))
_ATIPICAS = ("periodo", "puesto", "tarifa", "total_cobrado", "distancia_millas", "hora", "forma_pago", "zona_origen",
             "zona_destino")
_ATIPICAS_FMT = (("tarifa", USD), ("total_cobrado", USD), ("distancia_millas", DOS))
_CALIDAD = ("periodo", "archivo", "filas_archivo", "leidas", "aceptadas", "cuarentena", "pct_cuarentena",
            "con_advertencias", "pct_advertencias", "reconcilia", "fuente")
_CALIDAD_FMT = (("filas_archivo", ENTERO), ("leidas", ENTERO), ("aceptadas", ENTERO), ("cuarentena", ENTERO),
                ("pct_cuarentena", PCT), ("con_advertencias", ENTERO), ("pct_advertencias", PCT))
_REGLAS = ("regla", "severidad", "descripcion", "umbral", "filas_mes", "pct_mes", "filas_anterior", "pct_anterior", "cambio_pp")
_REGLAS_FMT = (("filas_mes", ENTERO), ("pct_mes", PCT), ("filas_anterior", ENTERO), ("pct_anterior", PCT), ("cambio_pp", PCT_SIGNO))
_ESQUEMA = ("periodo", "novedad", "columna", "detalle", "valores")


def _kpi(codigo: str, titulo: str, indicador: str, columna: str, formato: str, muestra: str) -> Grafico:
    return Grafico(codigo, titulo, "ev_indicadores", "kpi", "resumen", muestra, metricas=((titulo, columna),),
                   filtro=ind(indicador), formatos=(("y", formato),), ancho=2, alto=26)


CATALOGO: tuple[Grafico, ...] = (
    # Resumen
    _kpi("E0.1", "Viajes válidos del mes", "viajes", "valor_mes", ENTERO, "viajes válidos del mes"),
    _kpi("E0.2", "Viajes válidos, mismo mes del año anterior", "viajes", "valor_anterior", ENTERO, "viajes válidos del mes de comparación"),
    _kpi("E0.3", "Variación de viajes (%)", "viajes", "variacion_pct", PCT_SIGNO, "variación interanual de los viajes"),
    _kpi("E0.4", "Recaudación del mes (USD)", "recaudacion", "valor_mes", "$,.1f", "recaudación total del mes"),
    _kpi("E0.5", "Recaudación, mismo mes del año anterior (USD)", "recaudacion", "valor_anterior", "$,.1f", "recaudación total del mes de comparación"),
    _kpi("E0.6", "Variación de la recaudación (%)", "recaudacion", "variacion_pct", PCT_SIGNO, "variación interanual de la recaudación"),
    Grafico("E0.7", "Viajes por día del mes", "ev_dias", "lineas", "resumen", "volumen diario de los dos meses",
            x="dia", metricas=(("Viajes", "viajes"),), serie="periodo", formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=50,
            eje_x="Día del mes", eje_y="Viajes"),
    Grafico("E0.8", "Recaudación por día del mes (USD)", "ev_dias", "lineas", "resumen", "recaudación diaria de los dos meses",
            x="dia", metricas=(("Recaudación", "recaudacion"),), serie="periodo", formatos=(("y", "$,.3s"),), ancho=6, alto=50,
            eje_x="Día del mes", eje_y="USD"),
    # Calidad
    Grafico("EC.1", "Reconciliación: leídas = aceptadas + cuarentena", "ev_calidad", "tabla", "calidad",
            "filas leídas, aceptadas, en cuarentena y con advertencias de cada archivo", columnas=_CALIDAD,
            formatos=_CALIDAD_FMT, orden=(("periodo", False),), alto=26),
    Grafico("EC.2", "Filas que violan cada regla de calidad", "ev_reglas", "tabla", "calidad",
            "filas y porcentaje por regla en los dos meses", columnas=_REGLAS, formatos=_REGLAS_FMT, orden=(("regla", True),), alto=52),
    Grafico("EC.3", "Porcentaje de las filas leídas que viola cada regla", "ev_reglas", "barras", "calidad",
            "comparación visual de las reglas", x="regla", metricas=((MES, "pct_mes"), (ANTERIOR, "pct_anterior")),
            formatos=(("y", PCT),), ancho=6, alto=50, eje_x="Regla", eje_y="% de las filas leídas"),
    Grafico("EC.4", "Contrato de esquema: novedades de cada archivo", "ev_esquema", "tabla", "calidad",
            "qué trajo cada parquet respecto del contrato y qué se hizo", columnas=_ESQUEMA,
            formatos=(("valores", ENTERO),), orden=(("periodo", False), ("orden", True)), ancho=6, alto=50),
    # 1. Zonas
    Grafico("E1.1", "Top 10 de zonas de pickup del mes", "ev_zonas", "tabla", "zonas", "respuesta de la pregunta 1",
            columnas=_ZONAS, formatos=_ZONAS_FMT, filtro=(("puesto_mes", "<=", 10),), orden=(("puesto_mes", True),), ancho=6, alto=56),
    Grafico("E1.2", "Viajes del top 10, los dos meses", "ev_zonas", "barras", "zonas", "comparación visual del top 10",
            x="zona", metricas=_DOS_MESES, filtro=(("puesto_mes", "<=", 10),), orden=(("puesto_mes", True),),
            formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=56, eje_x="Zona de pickup", eje_y="Viajes"),
    Grafico("E1.3", "Top 10 del mismo mes del año anterior", "ev_zonas", "tabla", "zonas", "quién encabezaba, quién entra y quién sale",
            columnas=("puesto_anterior", "zona", "borough", "viajes_anterior", "viajes_mes", "variacion_pct", "puesto_mes"),
            formatos=_ZONAS_FMT, filtro=(("puesto_anterior", "<=", 10),), orden=(("puesto_anterior", True),), ancho=6, alto=56),
    Grafico("E1.4", "Concentración y composición del top 10", "ev_indicadores", "tabla", "zonas",
            "peso del top 10, zonas en Manhattan, zonas que crecen o caen y total de la ciudad", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("pickups", "top10_viajes", "top10_participacion", "top10_zonas", "top10_manhattan", "top10_crecen", "top10_caen",
                       "top10_estables", "top10_entran", "top10_salen"), orden=(("orden", True),), ancho=6, alto=56),
    Grafico("E1.5", "Pickups en JFK y LaGuardia", "ev_zonas", "tabla", "zonas", "puesto y variación de los dos aeropuertos",
            columnas=_ZONAS, formatos=_ZONAS_FMT, filtro=(("zona", "IN", ("JFK Airport", "LaGuardia Airport")),),
            orden=(("puesto_mes", True),), ancho=6, alto=30),
    Grafico("E1.6", "Pickups por borough", "ev_boroughs", "tabla", "zonas", "peso y variación de cada borough",
            columnas=("borough", "viajes_mes", "viajes_anterior", "variacion", "variacion_pct", "razon", "participacion_mes_pct",
                      "participacion_anterior_pct"),
            formatos=(("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("variacion", SIGNO), ("variacion_pct", PCT_SIGNO),
                      ("razon", DOS), ("participacion_mes_pct", PCT), ("participacion_anterior_pct", PCT)),
            orden=(("viajes_mes", False),), ancho=6, alto=44),
    Grafico("E1.7", "Variación de pickups por borough (%)", "ev_boroughs", "barras", "zonas", "comparación visual de los boroughs",
            x="borough", metricas=(("Variación %", "variacion_pct"),), formatos=(("y", PCT_SIGNO),), ancho=6, alto=44,
            eje_x="Borough", eje_y="% contra el año anterior"),
    Grafico("E1.8", "Todas las zonas y su variación", "ev_zonas", "tabla", "zonas", "detalle completo de zonas", columnas=_ZONAS,
            formatos=_ZONAS_FMT, orden=(("viajes_mes", False),), ancho=6, alto=44),
    # 2. Horas
    Grafico("E2.1", "Las 24 horas: volumen, ingreso por viaje, aeropuertos, distancia y atípicos", "ev_horas", "tabla", "horas",
            "respuesta de la pregunta 2 y sus causas, hora por hora",
            columnas=("hora", "viajes_mes", "viajes_anterior", "ingreso_viaje_mes", "ingreso_viaje_anterior", "variacion_ingreso_pct",
                      "puesto_mes", "puesto_anterior", "ingreso_sin_atipicas_mes", "ingreso_sin_atipicas_anterior", "tarifa_maxima_mes",
                      "tarifa_maxima_anterior", "pct_aeropuerto_mes", "pct_aeropuerto_anterior", "distancia_media_mes",
                      "distancia_media_anterior"),
            formatos=(("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("ingreso_viaje_mes", USD), ("ingreso_viaje_anterior", USD),
                      ("variacion_ingreso_pct", PCT_SIGNO), ("ingreso_sin_atipicas_mes", USD), ("ingreso_sin_atipicas_anterior", USD),
                      ("tarifa_maxima_mes", USD), ("tarifa_maxima_anterior", USD), ("pct_aeropuerto_mes", PCT),
                      ("pct_aeropuerto_anterior", PCT), ("distancia_media_mes", DOS), ("distancia_media_anterior", DOS)),
            orden=(("hora", True),), alto=90),
    Grafico("E2.2", "Ingreso promedio por viaje según la hora (USD)", "ev_horas", "lineas", "horas", "la hora con mayor ingreso",
            x="hora", metricas=((MES, "ingreso_viaje_mes"), (ANTERIOR, "ingreso_viaje_anterior")), formatos=(("y", USD),), ancho=6,
            alto=50, eje_x="Hora de pickup", eje_y="USD por viaje"),
    Grafico("E2.3", "Viajes según la hora", "ev_horas", "barras", "horas", "la hora pico de demanda", x="hora", metricas=_DOS_MESES,
            formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=50, eje_x="Hora de pickup", eje_y="Viajes"),
    Grafico("E2.4", "Viajes de aeropuerto según la hora (%)", "ev_horas", "lineas", "horas", "peso de JFK y LaGuardia en cada hora",
            x="hora", metricas=((MES, "pct_aeropuerto_mes"), (ANTERIOR, "pct_aeropuerto_anterior")), formatos=(("y", UNO),), ancho=6,
            alto=50, eje_x="Hora de pickup", eje_y="% de los viajes"),
    Grafico("E2.5", "Hora de mayor ingreso, hora pico y referencias del mes", "ev_indicadores", "tabla", "horas",
            "resumen de la pregunta 2", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("hora_mayor_ingreso", "ingreso_hora_mayor", "viajes_hora_mayor", "hora_pico", "viajes_hora_pico",
                       "participacion_aeropuertos", "distancia_media"), orden=(("orden", True),), ancho=6, alto=50),
    # 3. Peaje CBD
    Grafico("E3.1", "Peaje CBD: proporción de viajes, cobro y efecto del inicio", "ev_indicadores", "tabla", "peaje",
            "respuesta de la pregunta 3 (total del mes) y el efecto de la fecha de inicio", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("viajes", "viajes_con_peaje", "pct_con_peaje", "peaje_medio", "peaje_minimo", "viajes_con_dato_peaje",
                       "pct_viajes_antes_peaje", "pct_con_peaje_antes", "pct_con_peaje_desde"), orden=(("orden", True),), ancho=7, alto=46),
    Grafico("E3.5", "Regla R10: cobros anómalos del peaje", "ev_reglas", "tabla", "peaje", "filas marcadas por la regla R10",
            columnas=("regla", "descripcion", "filas_mes", "pct_mes", "filas_anterior", "pct_anterior", "cambio_pp"), formatos=_REGLAS_FMT,
            filtro=(("regla", "=", "R10"),), ancho=5, alto=46),
    Grafico("E3.3", "Las 5 zonas con mayor proporción de viajes con peaje", "ev_cbd_zonas", "tabla", "peaje",
            "respuesta de la pregunta 3 (zonas con 1.000 viajes o más)",
            columnas=("puesto", "zona", "borough", "viajes", "viajes_con_peaje", "pct_con_peaje", "variacion_viajes_pct"),
            formatos=(("viajes", ENTERO), ("viajes_con_peaje", ENTERO), ("pct_con_peaje", PCT), ("variacion_viajes_pct", PCT_SIGNO)),
            filtro=(("puesto", "<=", 5),), orden=(("puesto", True),), ancho=6, alto=40),
    Grafico("E3.4", "Las 15 zonas con mayor proporción de viajes con peaje (%)", "ev_cbd_zonas", "barras", "peaje",
            "comparación visual de las zonas", x="zona", metricas=(("% con peaje", "pct_con_peaje"),), filtro=(("puesto", "<=", 15),),
            orden=(("puesto", True),), formatos=(("y", UNO),), ancho=6, alto=40, eje_x="Zona de pickup", eje_y="% de los viajes"),
    Grafico("E3.2", "Proporción diaria de viajes con peaje (%)", "ev_dias", "lineas", "peaje", "cuándo empieza el cobro",
            x="dia", metricas=(("% con peaje", "pct_con_peaje"),), serie="periodo", formatos=(("y", UNO),), alto=50,
            eje_x="Día del mes", eje_y="% de los viajes"),
    # 4. Pagos
    Grafico("E4.1", "Propina como % de la tarifa, por forma de pago", "ev_pagos", "tabla", "pagos",
            "respuesta de la pregunta 4 y peso de cada forma de pago",
            columnas=("payment_type", "forma_pago", "viajes_tarifa_positiva_mes", "viajes_tarifa_positiva_anterior",
                      "propina_media_pct_mes", "propina_media_pct_anterior", "propina_ponderada_pct_mes", "propina_ponderada_pct_anterior",
                      "pct_con_propina_mes", "pct_con_propina_anterior", "viajes_mes", "viajes_anterior", "participacion_mes_pct",
                      "participacion_anterior_pct"),
            formatos=(("viajes_tarifa_positiva_mes", ENTERO), ("viajes_tarifa_positiva_anterior", ENTERO),
                      ("propina_media_pct_mes", PCT), ("propina_media_pct_anterior", PCT), ("propina_ponderada_pct_mes", PCT),
                      ("propina_ponderada_pct_anterior", PCT), ("pct_con_propina_mes", PCT), ("pct_con_propina_anterior", PCT),
                      ("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("participacion_mes_pct", PCT),
                      ("participacion_anterior_pct", PCT)),
            orden=(("payment_type", True),), alto=44),
    Grafico("E4.2", "Participación de cada forma de pago (%)", "ev_pagos", "barras", "pagos", "peso de cada forma de pago",
            x="forma_pago", metricas=((MES, "participacion_mes_pct"), (ANTERIOR, "participacion_anterior_pct")),
            formatos=(("y", UNO),), ancho=6, alto=50, eje_x="Forma de pago", eje_y="% de los viajes"),
    Grafico("E4.3", "Propina media por forma de pago (% de la tarifa)", "ev_pagos", "barras", "pagos", "propina de cada forma de pago",
            x="forma_pago", metricas=((MES, "propina_media_pct_mes"), (ANTERIOR, "propina_media_pct_anterior")),
            formatos=(("y", UNO),), ancho=6, alto=50, eje_x="Forma de pago", eje_y="% de la tarifa"),
    Grafico("E4.4", "Regla R05: viajes sin cantidad de pasajeros", "ev_reglas", "tabla", "pagos", "advertencias por passenger_count",
            columnas=("regla", "descripcion", "filas_mes", "pct_mes", "filas_anterior", "pct_anterior", "cambio_pp"), formatos=_REGLAS_FMT,
            filtro=(("regla", "=", "R05"),), alto=24),
    # 5. Aeropuertos
    Grafico("E5.1", "Viajes y tarifas de los aeropuertos", "ev_indicadores", "tabla", "aeropuertos", "respuesta de la pregunta 5",
            columnas=_IND, formatos=_IND_FMT,
            filtro=ind("viajes", "viajes_aeropuerto", "participacion_aeropuertos", "viajes_jfk", "viajes_lga", "tarifa_media_aeropuerto",
                       "tarifa_media_aeropuerto_sin_atipicas", "tarifa_mediana_aeropuerto", "tarifa_maxima_aeropuerto", "tarifa_fija_jfk"),
            orden=(("orden", True),), alto=52),
    Grafico("E5.2", "Viajes que tocan cada aeropuerto", "ev_indicadores", "barras", "aeropuertos", "JFK y LaGuardia en los dos meses",
            x="indicador", metricas=_VALORES, filtro=ind("viajes_jfk", "viajes_lga"), orden=(("orden", True),),
            formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=46, eje_x="Aeropuerto", eje_y="Viajes"),
    Grafico("E5.3", "Tarifa de los viajes de aeropuerto (USD)", "ev_indicadores", "barras", "aeropuertos",
            "media, media sin atípicas y mediana", x="indicador", metricas=_VALORES,
            filtro=ind("tarifa_media_aeropuerto", "tarifa_media_aeropuerto_sin_atipicas", "tarifa_mediana_aeropuerto"),
            orden=(("orden", True),), formatos=(("y", USD),), ancho=6, alto=46, eje_x="Tarifa", eje_y="USD"),
    Grafico("E5.4", "Las tarifas más altas de cada mes (mayores a US$ 500)", "ev_tarifas_altas", "tabla", "aeropuertos",
            "los viajes atípicos, con su recorrido y forma de pago", columnas=_ATIPICAS, formatos=_ATIPICAS_FMT,
            orden=(("periodo", False), ("puesto", True)), alto=36),
    # 6. Variación interanual
    Grafico("E6.1", "Viajes, recaudación, calendario y tarifas", "ev_indicadores", "tabla", "variacion", "respuesta de la pregunta 6",
            columnas=_IND, formatos=_IND_FMT,
            filtro=ind("viajes", "recaudacion", "dias_del_mes", "dias_con_viajes", "viajes_calendario_anterior", "tarifa_media",
                       "tarifa_media_sin_atipicas", "tarifa_mediana", "tarifa_maxima", "tarifas_sobre_tope"),
            orden=(("orden", True),), alto=52),
    Grafico("E6.2", "Efecto calendario: días de la semana de cada mes", "ev_dias_semana", "tabla", "variacion",
            "cuántas veces aparece cada día y sus viajes por día",
            columnas=("dia_semana", "dias_mes", "dias_anterior", "viajes_mes", "viajes_anterior", "viajes_por_dia_mes",
                      "viajes_por_dia_anterior", "variacion_por_dia_pct", "viajes_con_calendario_anterior"),
            formatos=(("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("viajes_por_dia_mes", UNO), ("viajes_por_dia_anterior", UNO),
                      ("variacion_por_dia_pct", PCT_SIGNO), ("viajes_con_calendario_anterior", UNO)),
            orden=(("dia_iso", True),), alto=44),
    Grafico("E6.3", "Viajes por día, según el día de la semana", "ev_dias_semana", "barras", "variacion", "comparación visual por día",
            x="dia_etiqueta", metricas=((MES, "viajes_por_dia_mes"), (ANTERIOR, "viajes_por_dia_anterior")), orden=(("dia_iso", True),),
            formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=46, eje_x="Día de la semana", eje_y="Viajes por día"),
    Grafico("E6.4", "Variación de los viajes por día (%)", "ev_dias_semana", "barras", "variacion", "si la variación es pareja o no",
            x="dia_etiqueta", metricas=(("Variación %", "variacion_por_dia_pct"),), orden=(("dia_iso", True),),
            formatos=(("y", PCT_SIGNO),), ancho=6, alto=46, eje_x="Día de la semana", eje_y="% contra el año anterior"),
    Grafico("E6.5", "Mezcla de viajes: Flex Fare, aeropuertos, viajes largos y distancia", "ev_indicadores", "tabla", "variacion",
            "qué cambió en la composición de los viajes", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("participacion_flex", "tarifa_flex", "tarifa_no_flex", "tarifa_flex_sin_atipicas", "tarifa_no_flex_sin_atipicas",
                       "participacion_aeropuertos", "pct_viajes_largos", "distancia_media", "duracion_media"),
            orden=(("orden", True),), alto=50),
    Grafico("E6.6", "Tarifa media, media sin atípicas y mediana (USD)", "ev_indicadores", "barras", "variacion",
            "comparación visual de las tarifas", x="indicador", metricas=_VALORES,
            filtro=ind("tarifa_media", "tarifa_media_sin_atipicas", "tarifa_mediana"), orden=(("orden", True),),
            formatos=(("y", USD),), alto=46, eje_x="Tarifa", eje_y="USD"),
    # Conclusiones: cada una tiene sus propios charts, al lado de su texto
    Grafico("C1.1", "Demanda: viajes y recaudación", "ev_indicadores", "tabla", "conclusiones", "conclusión 1, crecimiento o caída",
            columnas=_IND, formatos=_IND_FMT, filtro=ind("viajes", "recaudacion"), orden=(("orden", True),), ancho=6, alto=44),
    Grafico("C1.2", "Las 10 zonas que más mueven el total", "ev_zonas", "tabla", "conclusiones",
            "conclusión 1, zonas que más suman o pierden viajes",
            columnas=("puesto_aporte", "zona", "borough", "viajes_mes", "viajes_anterior", "variacion", "variacion_pct"),
            formatos=_ZONAS_FMT, filtro=(("puesto_aporte", "<=", 10),), orden=(("puesto_aporte", True),), ancho=6, alto=44),
    Grafico("C1.3", "Aeropuertos contra el total de la ciudad", "ev_zonas", "tabla", "conclusiones", "conclusión 1, aeropuertos",
            columnas=_ZONAS, formatos=_ZONAS_FMT, filtro=(("zona", "IN", ("JFK Airport", "LaGuardia Airport")),),
            orden=(("puesto_mes", True),), ancho=6, alto=30),
    Grafico("C2.1", "Alcance del peaje CBD en los dos meses", "ev_indicadores", "tabla", "conclusiones", "conclusión 2, alcance del peaje",
            columnas=_IND, formatos=_IND_FMT, filtro=ind("viajes_con_peaje", "pct_con_peaje", "viajes_con_dato_peaje"),
            orden=(("orden", True),), ancho=6, alto=36),
    Grafico("C2.2", "Zonas con mayor cobro: proporción y variación de sus viajes", "ev_cbd_zonas", "tabla", "conclusiones",
            "conclusión 2, demanda donde se cobra el peaje",
            columnas=("puesto", "zona", "borough", "pct_con_peaje", "viajes", "viajes_anterior", "variacion_viajes_pct"),
            formatos=(("pct_con_peaje", PCT), ("viajes", ENTERO), ("viajes_anterior", ENTERO), ("variacion_viajes_pct", PCT_SIGNO)),
            filtro=(("puesto", "<=", 5),), orden=(("puesto", True),), ancho=6, alto=36),
    Grafico("C3.1", "Perfil del viaje: distancia, tarifa, mezcla y propina", "ev_indicadores", "tabla", "conclusiones",
            "conclusión 3, viaje promedio", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("distancia_media", "tarifa_media", "tarifa_media_sin_atipicas", "tarifa_mediana", "participacion_flex",
                       "participacion_aeropuertos", "pct_viajes_largos", "propina_tarjeta"), orden=(("orden", True),), alto=46),
    Grafico("C4.1", "Peso de las tarifas atípicas en los promedios", "ev_indicadores", "tabla", "conclusiones",
            "conclusión 4, promedios con y sin atípicas", columnas=_IND, formatos=_IND_FMT,
            filtro=ind("tarifas_sobre_tope", "tarifas_sobre_tope_total", "tarifa_maxima", "tarifa_media", "tarifa_media_sin_atipicas",
                       "tarifa_media_aeropuerto", "tarifa_media_aeropuerto_sin_atipicas"), orden=(("orden", True),), ancho=6, alto=46),
    Grafico("C4.2", "Los viajes con las tarifas más altas", "ev_tarifas_altas", "tabla", "conclusiones", "conclusión 4, cuáles son",
            columnas=_ATIPICAS, formatos=_ATIPICAS_FMT, orden=(("periodo", False), ("puesto", True)), ancho=6, alto=46),
    Grafico("C5.1", "Cuarentena y reconciliación", "ev_calidad", "tabla", "conclusiones", "conclusión 5, calidad",
            columnas=_CALIDAD, formatos=_CALIDAD_FMT, orden=(("periodo", False),), alto=26),
    Grafico("C5.2", "Cambios de formato de los archivos", "ev_esquema", "tabla", "conclusiones", "conclusión 5, esquema",
            columnas=_ESQUEMA, formatos=(("valores", ENTERO),), orden=(("periodo", False), ("orden", True)), alto=30),
)

# --- catálogo: tablero anual (los 12 meses del año contra los 12 del año anterior) ---------------------------------
PESTANAS_ANUALES: tuple[tuple[str, str], ...] = (
    ("cobertura", "Cobertura y demanda"),
    ("tarifas", "Tarifas y viajes"),
    ("mezcla", "Peaje, pagos y aeropuertos"),
    ("detalle", "Detalle por mes"),
)


def _anual(codigo: str, titulo: str, tipo: str, pestana: str, indicador: str, formato: str, eje_y: str, muestra: str) -> Grafico:
    return Grafico(codigo, titulo, "ev_indicadores", tipo, pestana, muestra, x="mes", metricas=_VALORES, filtro=ind(indicador),
                   orden=(("mes", True),), formatos=(("y", formato),), ancho=6, alto=46, eje_x="Mes", eje_y=eje_y)


ANUALES: tuple[Grafico, ...] = (
    Grafico("A1", "Cobertura: los 12 meses del año y el estado de su comparación", "ev_cobertura", "tabla", "cobertura",
            "qué meses se pueden comparar con lo cargado",
            columnas=("mes", "mes_anterior", "estado", "viajes_mes", "viajes_anterior", "variacion_pct"),
            formatos=(("viajes_mes", ENTERO), ("viajes_anterior", ENTERO), ("variacion_pct", PCT_SIGNO)), orden=(("mes", True),),
            ancho=6, alto=62),
    Grafico("A2", "Viajes por mes: el año contra el año anterior", "ev_cobertura", "barras", "cobertura", "demanda de los 12 meses",
            x="mes", metricas=_DOS_MESES, orden=(("mes", True),), formatos=(("y", "SMART_NUMBER"),), ancho=6, alto=62, eje_x="Mes",
            eje_y="Viajes"),
    Grafico("A3", "Variación interanual de los viajes (%)", "ev_cobertura", "barras", "cobertura", "variación de los 12 meses",
            x="mes", metricas=(("Variación %", "variacion_pct"),), orden=(("mes", True),), formatos=(("y", PCT_SIGNO),), ancho=6, alto=46,
            eje_x="Mes", eje_y="% contra el año anterior"),
    _anual("A4", "Recaudación por mes (USD)", "barras", "cobertura", "recaudacion", "$,.3s", "USD", "recaudación de los 12 meses"),
    _anual("A5", "Tarifa media sin atípicas (USD)", "lineas", "tarifas", "tarifa_media_sin_atipicas", USD, "USD", "tarifa media de los 12 meses"),
    _anual("A6", "Tarifa mediana (USD)", "lineas", "tarifas", "tarifa_mediana", USD, "USD", "tarifa mediana de los 12 meses"),
    _anual("A7", "Distancia media (millas)", "lineas", "tarifas", "distancia_media", DOS, "Millas", "distancia media de los 12 meses"),
    _anual("A8", "Ingreso por viaje en la hora de mayor ingreso (USD)", "lineas", "tarifas", "ingreso_hora_mayor", USD, "USD por viaje",
           "pregunta 2 en los 12 meses"),
    _anual("A9", "Viajes con peaje CBD (%)", "lineas", "mezcla", "pct_con_peaje", UNO, "% de los viajes", "pregunta 3 en los 12 meses"),
    _anual("A10", "Participación de Flex Fare (%)", "lineas", "mezcla", "participacion_flex", UNO, "% de los viajes", "Flex Fare en los 12 meses"),
    _anual("A11", "Propina media con tarjeta (% de la tarifa)", "lineas", "mezcla", "propina_tarjeta", UNO, "% de la tarifa",
           "pregunta 4 en los 12 meses"),
    _anual("A12", "Viajes que tocan JFK o LaGuardia", "barras", "mezcla", "viajes_aeropuerto", "SMART_NUMBER", "Viajes",
           "pregunta 5 en los 12 meses"),
    _anual("A13", "Participación de los viajes de aeropuerto (%)", "lineas", "mezcla", "participacion_aeropuertos", UNO, "% de los viajes",
           "peso de los aeropuertos en los 12 meses"),
    _anual("A14", "Filas en cuarentena (% de las leídas)", "lineas", "mezcla", "pct_cuarentena", PCT, "% de las filas leídas",
           "calidad de los 12 meses"),
    Grafico("A15", "Todos los indicadores, mes por mes", "ev_indicadores", "tabla", "detalle", "todas las cifras de los 12 meses",
            columnas=("mes", "grupo", "indicador", "unidad", "valor_mes", "valor_anterior", "variacion", "variacion_pct"), formatos=_IND_FMT,
            orden=(("mes", True), ("orden", True)), alto=80),
    Grafico("A16", "Zona líder de cada mes", "ev_zonas", "tabla", "detalle", "pregunta 1 en los 12 meses",
            columnas=("mes", "zona", "borough", "viajes_mes", "viajes_anterior", "variacion_pct", "puesto_anterior"), formatos=_ZONAS_FMT,
            filtro=(("puesto_mes", "=", 1),), orden=(("mes", True),), ancho=6, alto=50),
    Grafico("A17", "Hora de mayor ingreso por viaje de cada mes", "ev_horas", "tabla", "detalle", "pregunta 2 en los 12 meses",
            columnas=("mes", "hora", "viajes_mes", "ingreso_viaje_mes", "ingreso_viaje_anterior", "variacion_ingreso_pct", "puesto_anterior"),
            formatos=(("viajes_mes", ENTERO), ("ingreso_viaje_mes", USD), ("ingreso_viaje_anterior", USD), ("variacion_ingreso_pct", PCT_SIGNO)),
            filtro=(("puesto_mes", "=", 1),), orden=(("mes", True),), ancho=6, alto=50),
)

POR_CODIGO: dict[str, Grafico] = {g.codigo: g for g in (*CATALOGO, *ANUALES)}
TABLAS: tuple[str, ...] = tuple(dict.fromkeys(g.tabla for g in (*CATALOGO, *ANUALES)))
TABLAS_MES: tuple[str, ...] = tuple(dict.fromkeys(g.tabla for g in CATALOGO))

# Qué charts respaldan cada bloque del reporte. La auditoría busca cada número solo en los charts de su bloque.
CITAS: dict[str, tuple[str, ...]] = {
    "resumen": ("E0.1", "E0.2", "E0.3", "E0.4", "E0.6"),
    "calidad_conteos": ("EC.1",),
    "calidad_reglas": ("EC.2",),
    "calidad_lectura": ("EC.1", "EC.2"),
    "esquema": ("EC.4",),
    "q1_tabla": ("E1.1",),
    "q1": ("E1.1", "E1.3", "E1.4", "E1.5", "E1.6"),
    "q2_tabla": ("E2.1",),
    "q2": ("E2.1", "E2.5"),
    "q3_tabla": ("E3.1", "E3.3"),
    "q3": ("E3.1", "E3.2", "E3.3", "E3.5"),
    "q4_tabla": ("E4.1",),
    "q4": ("E4.1", "E4.4"),
    "q5_tabla": ("E5.1",),
    "q5": ("E5.1", "E5.4"),
    "q6_tabla": ("E6.1",),
    "q6_volumen": ("E6.1",),
    "q6_calendario": ("E6.2", "E6.1"),
    "q6_tarifa": ("E6.1", "E5.4"),
    "q6_mezcla": ("E6.5",),
    "q6_calidad": ("EC.1", "EC.2"),
    "c_demanda": ("C1.1", "C1.2", "C1.3"),
    "c_peaje": ("C2.1", "C2.2"),
    "c_perfil": ("C3.1",),
    "c_atipicos": ("C4.1", "C4.2", "E2.1"),
    "c_calidad": ("C5.1", "C5.2"),
}


# --- evidencia de un mes ------------------------------------------------------------------------------------------
def a_python(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, datetime):
        return valor.date()
    return valor


@dataclass
class Evidencia:
    """Filas de marts.ev_* de una comparación. Vacía = ese mes no se puede comparar con lo que hay cargado."""

    mes: Month
    tablas: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @property
    def existe(self) -> bool:
        return bool(self.tablas.get("ev_indicadores"))

    def indicador(self, indicador_id: str) -> dict[str, Any]:
        for row in self.tablas.get("ev_indicadores", []):
            if row["indicador_id"] == indicador_id:
                return row
        raise KeyError(f"{indicador_id} no está en ev_indicadores de {self.mes}")


def leer(ejecutar: Query, mes: Month, tablas: Iterable[str] = TABLAS_MES) -> Evidencia:
    """Una consulta chica por tabla: select * from marts.ev_x where mes = 'YYYY-MM'."""
    evidencia = Evidencia(mes)
    for tabla in tablas:
        columnas, filas = ejecutar(f"select * from marts.{tabla} where mes = '{mes.label}'")
        evidencia.tablas[tabla] = [dict(zip(columnas, map(a_python, fila))) for fila in filas]
    return evidencia


def leer_anio(ejecutar: Query, anio: int) -> tuple[Evidencia, dict[str, Evidencia]]:
    """La evidencia del año completo (charts del tablero anual) y, por mes, la de cada comparación del año."""
    completo = Evidencia(Month(anio, 1))
    por_mes: dict[str, Evidencia] = {}
    for tabla in TABLAS:
        columnas, filas = ejecutar(f"select * from marts.{tabla} where anio = {anio}")
        rows = [dict(zip(columnas, map(a_python, fila))) for fila in filas]
        completo.tablas[tabla] = rows
        if tabla in TABLAS_MES:
            for row in rows:
                evidencia = por_mes.setdefault(str(row["mes"]), Evidencia(Month.parse(str(row["mes"]))))
                evidencia.tablas.setdefault(tabla, []).append(row)
    return completo, dict(sorted(por_mes.items()))


def meses_comparables(ejecutar: Query, anio: int | None = None) -> list[Month]:
    """Meses cuya comparación interanual está completa en el warehouse."""
    _, filas = ejecutar("select mes from marts.ev_comparaciones order by mes")
    meses = [Month.parse(str(fila[0])) for fila in filas]
    return [m for m in meses if anio is None or m.year == anio]


# --- tableros -------------------------------------------------------------------------------------------------------
def motor(settings: Settings) -> str:
    """Cada motor tiene sus propios tableros: un reporte local y uno de la nube nunca se pisan el respaldo."""
    return "local" if settings.warehouse == "duckdb" else "nube"


def slug_mes(settings: Settings, mes: Month) -> str:
    return f"respaldo-{motor(settings)}-{mes.label}"


def slug_anio(settings: Settings, anio: int) -> str:
    return f"respaldo-{motor(settings)}-{anio}"


def url_tablero(base: str, slug: str, ancla: str = "") -> str:
    return f"{base.rstrip('/')}/superset/dashboard/{slug}/" + (f"#{ancla}" if ancla else "")


def enlace(grafico: Grafico) -> str:
    """Enlace por referencia a un chart: su dirección está una sola vez, al final del reporte (referencias)."""
    return f"[{grafico.codigo} {grafico.titulo}][{grafico.codigo}]"


def citas(clave: str) -> str:
    return " · ".join(enlace(POR_CODIGO[codigo]) for codigo in CITAS[clave])


def cita(clave: str) -> str:
    """La línea "Respaldo en Superset" que cierra cada bloque del reporte."""
    return f"**Respaldo en Superset:** {citas(clave)}"


def referencias(base: str, slug: str) -> list[str]:
    """La dirección de cada chart (el tablero del mes, abierto en ese chart)."""
    return [f"[{g.codigo}]: {url_tablero(base, slug, g.componente)}" for g in CATALOGO]


def seccion_corta(seccion: str) -> str:
    """"3. Proporción de viajes..." -> "Pregunta 3"; "Calidad de los datos y cuarentena" -> "Calidad"."""
    m = re.match(r"(\d)\. ", seccion)
    return f"Pregunta {m.group(1)}" if m else "Calidad" if seccion.startswith("Calidad") else seccion


# --- reconciliación de sql/q1..q6 con la evidencia ---------------------------------------------------------------------
class EvidenciaError(RuntimeError):
    """Las respuestas de sql/q1..q6 y las tablas de evidencia no dan lo mismo: no se publica el reporte."""


def _difiere(a: Any, b: Any, tolerancia: float) -> bool:
    if a is None or b is None:
        return not (a in (None, 0) and b in (None, 0))
    return abs(float(a) - float(b)) > tolerancia


def reconciliar(preguntas: list[dict[str, Any]], evidencia: Evidencia) -> list[str]:
    """Compara cada celda de las seis respuestas con la evidencia. Los conteos deben ser idénticos; los montos y
    porcentajes, que las preguntas redondean a 2 decimales, iguales al centavo. Devuelve las diferencias."""
    problemas: list[str] = []
    q = {r["index"]: r["records"] for r in preguntas}
    anio = evidencia.mes.year

    def comparar(donde: str, valor: Any, evidencia_valor: Any, tolerancia: float = 0.0) -> None:
        if _difiere(valor, evidencia_valor, tolerancia):
            problemas.append(f"{donde}: la pregunta da {valor} y la evidencia {evidencia_valor}")

    centavo = 0.00501
    zonas = sorted((z for z in evidencia.tablas["ev_zonas"] if z["puesto_mes"] and z["puesto_mes"] <= 10), key=lambda z: z["puesto_mes"])
    if len(q[1]) != len(zonas):
        problemas.append(f"q1: {len(q[1])} zonas en la respuesta y {len(zonas)} en la evidencia")
    for fila, zona in zip(q[1], zonas):
        comparar(f"q1 puesto {zona['puesto_mes']} ({fila['pickup_zone']}), viajes del mes", fila["trips_assigned"], zona["viajes_mes"])
        if fila["pickup_zone"] == zona["zona"]:  # con un empate exacto el orden de dos zonas puede diferir
            comparar(f"q1 {zona['zona']}, viajes del año anterior", fila["trips_comparison"], zona["viajes_anterior"])
            if fila["trips_change_pct"] is not None:
                comparar(f"q1 {zona['zona']}, variación %", fila["trips_change_pct"], zona["variacion_pct"], centavo)
    horas = {h["hora"]: h for h in evidencia.tablas["ev_horas"]}
    for fila in q[2]:
        rol = "mes" if int(fila["year"]) == anio else "anterior"
        hora = horas.get(int(fila["pickup_hour"]), {})
        comparar(f"q2 {fila['year']}, viajes de las {fila['pickup_hour']}:00", fila["trips"], hora.get(f"viajes_{rol}"))
        comparar(f"q2 {fila['year']}, ingreso por viaje", fila["avg_revenue_per_trip"], hora.get(f"ingreso_viaje_{rol}"), centavo)
    # Por puesto y no por nombre: hay zonas distintas con el mismo nombre (Corona es 56 y 57).
    peaje = {z["puesto"]: z for z in evidencia.tablas["ev_cbd_zonas"]}
    for puesto, fila in enumerate(q[3]):
        if fila["scope"] == "ALL ZONES":
            comparar("q3 total, viajes", fila["trips"], evidencia.indicador("viajes")["valor_mes"])
            comparar("q3 total, viajes con peaje", fila["trips_with_cbd_fee"], evidencia.indicador("viajes_con_peaje")["valor_mes"])
            comparar("q3 total, % con peaje", fila["pct_with_cbd_fee"], evidencia.indicador("pct_con_peaje")["valor_mes"], centavo)
            continue
        zona = peaje.get(puesto, {})
        comparar(f"q3 puesto {puesto} ({fila['scope']}), viajes", fila["trips"], zona.get("viajes"))
        comparar(f"q3 puesto {puesto} ({fila['scope']}), viajes con peaje", fila["trips_with_cbd_fee"], zona.get("viajes_con_peaje"))
        comparar(f"q3 puesto {puesto} ({fila['scope']}), % con peaje", fila["pct_with_cbd_fee"], zona.get("pct_con_peaje"), centavo)
    pagos = {p["payment_type"]: p for p in evidencia.tablas["ev_pagos"]}
    for fila in q[4]:
        rol = "mes" if int(fila["year"]) == anio else "anterior"
        pago = pagos.get(fila["payment_type"], {})
        donde = f"q4 {fila['year']} {fila['payment_type_name']}"
        comparar(f"{donde}, viajes", fila["trips"], pago.get(f"viajes_tarifa_positiva_{rol}"))
        comparar(f"{donde}, propina %", fila["avg_tip_pct"], pago.get(f"propina_media_pct_{rol}"), centavo)
        comparar(f"{donde}, propina ponderada %", fila["weighted_tip_pct"], pago.get(f"propina_ponderada_pct_{rol}"), centavo)
    for fila in q[5]:
        rol = "valor_mes" if int(fila["year"]) == anio else "valor_anterior"
        for columna, indicador, tolerancia in (("airport_trips", "viajes_aeropuerto", 0.0), ("trips_touching_jfk", "viajes_jfk", 0.0),
                                               ("trips_touching_lga", "viajes_lga", 0.0), ("avg_fare_amount", "tarifa_media_aeropuerto", centavo)):
            comparar(f"q5 {fila['year']}, {columna}", fila[columna], evidencia.indicador(indicador)[rol], tolerancia)
    for fila in q[6]:
        viajes, tarifa = evidencia.indicador("viajes"), evidencia.indicador("tarifa_media")
        comparar("q6, viajes del mes", fila["trips_assigned"], viajes["valor_mes"])
        comparar("q6, viajes del año anterior", fila["trips_comparison"], viajes["valor_anterior"])
        comparar("q6, variación de viajes %", fila["trips_change_pct"], viajes["variacion_pct"], centavo)
        comparar("q6, tarifa media del mes", fila["avg_fare_assigned"], tarifa["valor_mes"], centavo)
        comparar("q6, tarifa media del año anterior", fila["avg_fare_comparison"], tarifa["valor_anterior"], centavo)
        comparar("q6, variación de la tarifa %", fila["avg_fare_change_pct"], tarifa["variacion_pct"], centavo)
    return problemas


# --- auditoría: cada número del .md contra los charts que cita su bloque ----------------------------------------------
@dataclass
class Celda:
    codigo: str
    columna: str
    fila: str
    valor: float


@dataclass
class Cifra:
    """Un número del reporte y dónde se ve en Superset (celdas vacías = ningún chart citado lo muestra)."""

    seccion: str
    texto: str
    citados: tuple[str, ...]
    celdas: list[Celda] = field(default_factory=list)

    @property
    def respaldada(self) -> bool:
        return bool(self.celdas)


_TEXTO_FILA = ("indicador", "zona", "borough", "forma_pago", "dia_semana", "regla", "novedad")


def _fila(grafico: Grafico, row: dict[str, Any]) -> str:
    """Nombre legible de una fila de un chart: 'Midtown Center', '5:00', '2024-01 puesto 1'..."""
    if "hora" in row and grafico.tabla == "ev_horas":
        return f"{row['hora']}:00"
    partes = [str(row[c]) for c in ("periodo",) if row.get(c)]
    partes += [str(row[c]) for c in _TEXTO_FILA if row.get(c)]
    if grafico.tabla == "ev_tarifas_altas":
        partes.append(f"puesto {row['puesto']}")
    if grafico.tabla == "ev_dias":
        partes.append(f"día {row['dia']}")
    if grafico.tabla == "ev_esquema" and row.get("columna"):
        partes.append(str(row["columna"]))
    return " ".join(partes)


def celdas(grafico: Grafico, evidencia: Evidencia) -> list[Celda]:
    """Todos los valores numéricos que muestra el chart en ese mes."""
    out = []
    for row in grafico.filas(evidencia):
        for columna in grafico.columnas_datos:
            valor = row.get(columna)
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                out.append(Celda(grafico.codigo, columna, _fila(grafico, row), float(valor)))
    return out


# Lo que no es una cifra del mes: nombres de reglas, códigos de la TLC, umbrales fijos, fechas, años y nombres de archivo.
_NO_CIFRAS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"```.*?```", r"`[^`]*`", r"\]\([^)]*\)", r"<[^>]+>",
    r"\b\d{4}-\d{2}(?:-\d{2})?\b",                                 # 2025-01, 2025-01-05
    r"\bR\d{2}\b", r"\bQ\d\b", r"payment_type \d", r"RatecodeID \d", r"\btop \d+",
    r"(?:mayores? a|superan(?: los)?) US\$ ?500",                  # FARE_CAP: umbral, no resultado
    r"m[aá]s de 10 millas",                                         # umbral de viaje largo
    r"\(26[45]\)", r"\bzona \d+", r"\bla 265\b", r"anterior a 2011",
    r"\bdel 1 al \d{1,2}\b",                                       # fechas del inicio del peaje: "del 1 al 4",
    r"\bel \d{1,2}(?![\d.,]*\d)(?! ?[%\d])(?: de [a-z]+(?: de \d{4})?)?",  # "el 5 de enero", "desde el 5" (nunca "el 20,8 %")
    r"(?<![\d.,])(?:19|20)\d{2}(?![\d.,]*\d)",                     # años
))
_HORA = re.compile(r"\b(\d{1,2}):00\b")
_NUMERO = re.compile(r"(?<![\w.,])([+−±-]?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?( M\b)?")
_CODIGOS = re.compile(r"\[((?:E[\dC]|C\d|A)\.?\d+) ")
_RESPALDO = re.compile(r"\*\*Respaldo en Superset:\*\*|_Respaldo:_")
SECCION_RESPALDO = "## Respaldo en Superset"


def numeros(texto: str) -> list[tuple[str, str, float, int, float]]:
    """(texto, signo, valor, decimales, escala) de cada cifra de un texto en español (punto = miles, coma = decimales)."""
    for patron in _NO_CIFRAS:
        texto = patron.sub(" ", texto)
    out: list[tuple[str, str, float, int, float]] = []
    for m in _HORA.finditer(texto):
        out.append((m.group(0), "", float(m.group(1)), 0, 1.0))
    texto = _HORA.sub(" ", texto)
    for m in _NUMERO.finditer(texto):
        signo, entero, decimales, millones = m.groups()
        if entero == "0" and not decimales:
            continue  # "no en 0", "cercana a 0": palabras, no una cifra
        valor = float(entero.replace(".", "") + ("." + decimales if decimales else ""))
        out.append((m.group(0).strip(), signo.replace("−", "-"), valor, len(decimales or ""), 1e6 if millones else 1.0))
    return out


def coincide(celda: float, signo: str, valor: float, decimales: int, escala: float) -> bool:
    """La celda, redondeada como en el texto, es el número del texto (con su signo, si lo escribe)."""
    if f"{abs(celda) / escala:.{decimales}f}" != f"{valor:.{decimales}f}":
        return False
    if signo == "+":
        return celda >= 0
    if signo == "-":
        return celda <= 0
    return True


def bloques(texto: str) -> list[tuple[str, str, tuple[str, ...]]]:
    """(sección, texto, charts citados) de cada bloque del reporte. Un bloque termina en su línea de respaldo; lo que
    quede sin ella hasta el título siguiente es un bloque sin charts. La sección del respaldo no se audita."""
    cuerpo = texto.split(f"\n{SECCION_RESPALDO}", 1)[0]
    cuerpo = re.sub(r"```.*?```", "", cuerpo, flags=re.DOTALL)
    cuerpo = re.sub(r"^\| \| \|\n\|---\|---\|\n(?:\|.*\n)+", "", cuerpo, flags=re.MULTILINE)  # ficha de la corrida
    out: list[tuple[str, str, tuple[str, ...]]] = []
    seccion, lineas = "Resumen", []

    def cerrar(citados: tuple[str, ...] = ()) -> None:
        contenido = "\n".join(lineas).strip()
        if contenido:
            out.append((seccion, contenido, citados))
        lineas.clear()

    for linea in cuerpo.splitlines():
        if linea.startswith("## "):
            cerrar()
            seccion = linea[3:].strip()
        elif linea.startswith("# ") or linea.startswith("Consulta: ") or re.match(r"^\|[-:| ]+\|$", linea):
            continue
        elif _RESPALDO.search(linea):
            cerrar(tuple(dict.fromkeys(_CODIGOS.findall(linea))))
        else:
            lineas.append(linea)
    cerrar()
    return out


def _sin_codigos_de_tabla(texto: str) -> str:
    """En las tablas de las preguntas, year y month son la clave de la fila, no una cifra."""
    lineas, omitir = [], set()
    for linea in texto.splitlines():
        if linea.startswith("|"):
            celdas_linea = [c.strip() for c in linea.strip().strip("|").split("|")]
            if {"year", "month"} & set(celdas_linea):
                omitir = {i for i, c in enumerate(celdas_linea) if c in {"year", "month"}}
            lineas.append("| " + " | ".join("" if i in omitir else c for i, c in enumerate(celdas_linea)) + " |")
        else:
            omitir = set()
            lineas.append(linea)
    return "\n".join(lineas)


def auditar(texto: str, evidencia: Evidencia) -> list[Cifra]:
    """Cada número del reporte y las celdas de los charts citados por su bloque donde se ve ese número."""
    por_grafico = {g.codigo: celdas(g, evidencia) for g in CATALOGO}
    cifras: list[Cifra] = []
    for seccion, contenido, citados in bloques(texto):
        disponibles = [c for codigo in citados for c in por_grafico.get(codigo, [])]
        for escrito, signo, valor, decimales, escala in numeros(_sin_codigos_de_tabla(contenido)):
            halladas = [c for c in disponibles if coincide(c.valor, signo, valor, decimales, escala)]
            cifras.append(Cifra(seccion, escrito, citados, halladas))
    return cifras


def contrastes(conteos: dict[str, int], evidencia: Evidencia) -> list[str]:
    """Los conteos que el texto escribe con palabras ("nueve de las diez zonas...") contra la evidencia."""
    return [f"{indicador}: el texto usa {valor} y la evidencia {evidencia.indicador(indicador)['valor_mes']}"
            for indicador, valor in conteos.items() if _difiere(valor, evidencia.indicador(indicador)["valor_mes"], 0.0)]


# --- sección "Respaldo en Superset" del reporte -----------------------------------------------------------------------
VERIFICACION_INICIO = "<!-- VERIFICACION:START - la escribe src/respaldo.py al comparar el reporte con Superset; no editar a mano -->"
VERIFICACION_FIN = "<!-- VERIFICACION:END -->"
PENDIENTE = ("**Verificación contra Superset:** pendiente. Este reporte todavía no se comparó con lo que muestran los charts (Superset no "
             "estaba disponible o su paso no terminó). Con el stack arriba (`docker compose up -d`), `make superset-dashboards {args}` crea "
             "o actualiza los tableros, los compara y completa este bloque.")


def argumentos_make(settings: Settings, mes: Month) -> str:
    modo = (" INGEST_MODE=direct" if settings.offline else "") + (" WAREHOUSE=duckdb" if settings.warehouse == "duckdb" else "")
    return f"MES={mes}{modo}"


def bloque_verificacion(contenido: str) -> str:
    return f"{VERIFICACION_INICIO}\n{contenido}\n{VERIFICACION_FIN}"


def reemplazar_verificacion(texto: str, contenido: str) -> str | None:
    inicio, fin = texto.find("<!-- VERIFICACION:START"), texto.find(VERIFICACION_FIN)
    if inicio < 0 or fin < inicio:
        return None
    return texto[:inicio] + bloque_verificacion(contenido) + texto[fin + len(VERIFICACION_FIN):]


def estado_verificacion(path: Path) -> str:
    """La primera línea del bloque de verificación de un reporte, sin formato."""
    texto = path.read_text(encoding="utf-8") if path.exists() else ""
    m = re.search(r"<!-- VERIFICACION:START[^\n]*\n([^\n]+)", texto)
    return m.group(1).replace("**", "") if m else ""


def _dato(celda: Celda) -> str:
    return f"`{celda.columna}`" + (f" · {celda.fila}" if celda.fila else "")


def seccion_respaldo(settings: Settings, mes: Month, base: str, cifras: list[Cifra], avisos: list[str]) -> list[str]:
    """Última sección del .md: tableros, resultado de la auditoría, índice de charts y cada cifra con su chart."""
    slug = slug_mes(settings, mes)
    citados = list(dict.fromkeys(c for codigos in CITAS.values() for c in codigos))
    secciones: dict[str, list[str]] = {}
    for cifra in cifras:
        for codigo in cifra.citados:
            nombres = secciones.setdefault(codigo, [])
            if seccion_corta(cifra.seccion) not in nombres:
                nombres.append(seccion_corta(cifra.seccion))
    sin_respaldo = [c for c in cifras if not c.respaldada]
    lineas = [
        SECCION_RESPALDO,
        "",
        f"Todas las cifras salen de las tablas `marts.ev_*` (modelos dbt de `dbt_taxi/models/evidence`), y los tableros leen esas "
        f"mismas tablas. Tablero de este mes: [`{slug}`]({url_tablero(base, slug)}). Los 12 meses de {mes.year} contra {mes.year - 1}: "
        f"[`{slug_anio(settings, mes.year)}`]({url_tablero(base, slug_anio(settings, mes.year))}). Los enlaces funcionan con el stack "
        "levantado (`docker compose up -d`).",
        "",
        f"**Auditoría de las cifras:** {len(cifras)} números en este reporte, {len(cifras) - len(sin_respaldo)} se ven en los charts que "
        f"cita su bloque y {len(sin_respaldo)} no." + (" Las respuestas de `sql/q1..q6` coinciden con la evidencia." if not avisos else ""),
        "",
    ]
    if sin_respaldo:
        lineas += ["Números que ningún chart citado muestra (no usarlos como respaldados):", ""]
        lineas += [f"- {c.texto} ({seccion_corta(c.seccion)})" for c in sin_respaldo] + [""]
    if avisos:
        lineas += ["Diferencias entre el texto y la evidencia:", ""] + [f"- {a}" for a in avisos] + [""]
    lineas += [bloque_verificacion(PENDIENTE.format(args=argumentos_make(settings, mes))), ""]
    lineas += ["| chart | qué sustenta | tabla | dónde se cita |", "|---|---|---|---|"]
    for codigo in citados:
        grafico = POR_CODIGO[codigo]
        lineas.append(f"| {enlace(grafico)} | {grafico.muestra} | `marts.{grafico.tabla}` | {', '.join(secciones.get(codigo, [])) or 'Calidad'} |")
    apoyo = [g for g in CATALOGO if g.codigo not in citados]
    lineas += ["", "Charts de apoyo visual del mismo tablero (mismas tablas): " + ", ".join(enlace(g) for g in apoyo) + ".", ""]
    lineas += ["<details><summary>Cada cifra y el chart donde se ve</summary>", "",
               "Cuando un número redondeado aparece en más de una celda se indica cuántas.", "",
               "| sección | cifra | chart | columna y fila |", "|---|---:|---|---|"]
    for cifra in cifras:
        if not cifra.celdas:
            lineas.append(f"| {seccion_corta(cifra.seccion)} | {cifra.texto} | sin respaldo | - |")
            continue
        primera = cifra.celdas[0]
        extra = f" (y {len(cifra.celdas) - 1} más)" if len(cifra.celdas) > 1 else ""
        lineas.append(f"| {seccion_corta(cifra.seccion)} | {cifra.texto} | {primera.codigo} | {_dato(primera)}{extra} |")
    lineas += ["", "</details>", "", *referencias(base, slug), ""]
    return lineas


def conclusiones_de(path: Path) -> list[tuple[str, str]]:
    """(grupo de charts, texto) de cada conclusión de un reporte ya escrito: su tablero muestra ese mismo texto. El
    grupo sale del respaldo que cita la conclusión: C1.1 -> "C1"."""
    if not path.exists():
        return []
    texto = path.read_text(encoding="utf-8")
    m = re.search(r"^## Conclusiones\n(.*?)(?=^## |\Z)", texto, flags=re.MULTILINE | re.DOTALL)
    out: list[tuple[str, str]] = []
    for linea in (m.group(1).splitlines() if m else []):
        if linea.startswith("- "):
            out.append(("", linea[2:].strip()))
        elif out and _RESPALDO.search(linea):
            grupos = [c.split(".")[0] for c in _CODIGOS.findall(linea) if c.startswith("C")]
            out[-1] = (grupos[0] if grupos else "", out[-1][1])
    return out


def motor_de(path: Path) -> str | None:
    """Con qué motor se escribió un reporte ("local" o "nube"), según el tablero de respaldo que declara."""
    if not path.exists():
        return None
    m = re.search(r"`respaldo-(local|nube)-\d{4}-\d{2}`", path.read_text(encoding="utf-8"))
    return m.group(1) if m else None
