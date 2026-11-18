"""Interpretación dinámica, en español, de la comparación mes asignado vs mismo mes del año anterior.

Nada de lo que se escribe acá es texto fijo: cada frase se arma con los números de la corrida.
src/resultados.py ejecuta las 6 preguntas (sql/q*.sql) y, además, las consultas de contexto de
sql/contexto/ (perfil del mes, zonas, horas, calendario, peaje CBD, pagos, aeropuertos, tarifas
atípicas). Con esos datos, más los reportes de esquema y de calidad de la base de control local
(qué traía cada parquet, qué se convirtió, qué se fue a cuarentena y por qué regla), este módulo
redacta:

  - un resumen de una frase,
  - la sección de calidad de datos y cuarentena,
  - la interpretación de cada pregunta (q1..q6),
  - las conclusiones.

Las reglas de redacción (umbrales para decir "se mantiene", "crece con fuerza", cuándo un atípico
merece una advertencia, etc.) están en este archivo y se prueban en tests/test_interpretacion.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from string import Template
from typing import Any, Callable

from src.config import SQL_DIR, Month, Settings, control_db, get_logger

log = get_logger("interpretacion")

CONTEXT_DIR = SQL_DIR / "contexto"
# Ninguna regla de calidad pone un tope a la tarifa (limitación documentada): los promedios se
# muestran también sin las tarifas mayores a este valor, para que un único viaje no cambie la lectura.
FARE_CAP = 500
AIRPORTS = ("JFK Airport", "LaGuardia Airport")
STABLE_PCT = 0.5  # |variación| menor a esto = "se mantiene"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábados", 7: "domingos"}
PAGOS = {0: "Flex Fare", 1: "tarjeta de crédito", 2: "efectivo", 3: "No charge", 4: "Dispute", 5: "Unknown",
         6: "Voided trip"}
NUMEROS = ["ninguna", "una", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez"]
ORDINALES = {1: "primer", 2: "segundo", 3: "tercer"}


# --- formato (español: punto = miles, coma = decimales) ----------------------------------------------
def _swap(text: str) -> str:
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def entero(value: float | int) -> str:
    return _swap(f"{int(round(value)):,}")


def decimal(value: float, digits: int = 2) -> str:
    return _swap(f"{value:,.{digits}f}")


def pct(value: float, digits: int = 1) -> str:
    return f"{decimal(value, digits)} %"


def signo(value: float, digits: int = 1, unit: str = " %") -> str:
    """+15,8 % / −2,6 % (signo menos tipográfico, como en un informe)."""
    rounded = round(value, digits)
    mark = "+" if rounded > 0 else "−" if rounded < 0 else "±"
    return f"{mark}{decimal(abs(value), digits)}{unit}"


def puntos(value: float, digits: int = 1) -> str:
    return signo(value, digits, " pp")


def usd(value: float, digits: int = 2) -> str:
    return f"US$ {decimal(value, digits)}"


def usd_millones(value: float) -> str:
    return f"US$ {decimal(value / 1e6, 1)} M" if abs(value) >= 1e6 else f"US$ {entero(value)}"


def mes_es(month: Month) -> str:
    return f"{MESES[month.month - 1]} {month.year}"


def hora(hour: int) -> str:
    return f"{'la' if int(hour) == 1 else 'las'} {int(hour)}:00"


def lista(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} y {items[-1]}"


def numero(n: int) -> str:
    return NUMEROS[n] if 0 <= n < len(NUMEROS) else entero(n)


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def variacion(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return 100.0 * (new - old) / old


def verbo(change: float | None, up: str = "sube", down: str = "baja", same: str = "se mantiene",
          stable: float = STABLE_PCT) -> str:
    if change is None or abs(change) < stable:
        return same
    return up if change > 0 else down


def intensidad(change: float) -> str:
    """Adjetivo para el tamaño de un cambio porcentual."""
    size = abs(change)
    return "con fuerza" if size >= 10 else "en forma moderada" if size >= 3 else "levemente"


def share(part: float | None, total: float | None) -> float:
    return 100.0 * (part or 0) / total if total else 0.0


# --- datos ---------------------------------------------------------------------------------------------------------
def _to_python(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.date() if value.hour == value.minute == value.second == 0 else value
    return value


def context_files() -> list[Path]:
    files = list(CONTEXT_DIR.glob("c*.sql"))
    return sorted(files, key=lambda p: int(re.match(r"c(\d+)", p.stem).group(1)))  # type: ignore[union-attr]


def render_context(path: Path, month: Month) -> str:
    params = {"YEAR": month.year, "MONTH": month.month, "CMP_YEAR": month.comparison.year, "FARE_CAP": FARE_CAP}
    return Template(path.read_text(encoding="utf-8")).substitute(params).strip().rstrip(";")


Query = Callable[[str], tuple[list[str], list[tuple]]]


def fetch_context(run: Query, month: Month) -> dict[str, list[dict[str, Any]]]:
    """Runs every sql/contexto/c*.sql. Key = file name without the cN_ prefix (perfil_mes, zonas...)."""
    data: dict[str, list[dict[str, Any]]] = {}
    for path in context_files():
        columns, rows = run(render_context(path, month))
        data[path.stem.split("_", 1)[1]] = [dict(zip(columns, map(_to_python, row))) for row in rows]
    return data


@dataclass
class CalidadMes:
    """Quality gate of one month: counts, every rule (reject and warning) and the schema report."""

    mes: str
    rows_read: int
    rows_accepted: int
    rows_quarantined: int
    rows_with_warnings: int | None  # None: only the warehouse was available (no warnings there)
    reconciled: bool
    rules: dict[str, int] = field(default_factory=dict)  # rule id -> rows violating it
    source: str = "control"  # control = local control database; warehouse = fallback
    schema: dict[str, Any] = field(default_factory=dict)
    ingestion: dict[str, Any] = field(default_factory=dict)

    def pct(self, rows: int | None) -> float:
        return share(rows, self.rows_read)


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def quality_from_control(settings: Settings, mes: str) -> CalidadMes | None:
    """Last quality run, schema report and ingestion of a month from the local control database."""
    if not settings.control_db.exists():
        return None
    con = control_db(settings)
    try:
        tables = {t for (t,) in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        if "quality_summary" not in tables:
            return None
        summary = con.execute(
            "SELECT run_id, rows_read, rows_accepted, rows_quarantined, rows_with_warnings, reconciled "
            "FROM quality_summary WHERE mes = ? ORDER BY created_at DESC LIMIT 1", [mes]).fetchone()
        if summary is None:
            return None
        run_id = summary[0]
        rules = dict(con.execute("SELECT rule_id, violations FROM quality_report WHERE mes = ? AND run_id = ?",
                                 [mes, run_id]).fetchall())
        schema: dict[str, Any] = {}
        if "schema_report" in tables:
            cursor = con.execute("SELECT * FROM schema_report WHERE dataset = 'yellow' AND mes = ? "
                                 "ORDER BY created_at DESC LIMIT 1", [mes])
            row = cursor.fetchone()
            if row is not None:
                schema = dict(zip([d[0] for d in cursor.description], row))
        ingestion: dict[str, Any] = {}
        if "ingestion_log" in tables:
            cursor = con.execute("SELECT file, bytes, sha256, row_count, mode, action, logged_at FROM ingestion_log "
                                 "WHERE dataset = 'yellow' AND mes = ? AND status = 'ok' ORDER BY logged_at DESC LIMIT 1",
                                 [mes])
            row = cursor.fetchone()
            if row is not None:
                ingestion = dict(zip([d[0] for d in cursor.description], row))
    finally:
        con.close()
    return CalidadMes(
        mes=mes, rows_read=int(summary[1]), rows_accepted=int(summary[2]), rows_quarantined=int(summary[3]),
        rows_with_warnings=int(summary[4]), reconciled=bool(summary[5]), rules={k: int(v) for k, v in rules.items()},
        schema={
            "status": schema.get("status"),
            "missing_optional": _json(schema.get("missing_optional"), []),
            "new_columns": _json(schema.get("new_columns"), []),
            "type_mismatches": _json(schema.get("type_mismatches"), {}),
            "cast_failures": _json(schema.get("cast_failures"), {}),
            "null_violations": _json(schema.get("null_violations"), {}),
            "value_mapped": _json(schema.get("value_mapped"), []),
            "derived": _json(schema.get("derived_columns"), {}),
        } if schema else {},
        ingestion=ingestion,
    )


def quality_from_warehouse(month: Month, year: int, data: dict[str, list[dict[str, Any]]]) -> CalidadMes | None:
    counts = next((r for r in data.get("cuarentena", []) if int(r["year"]) == year), None)
    if counts is None:
        return None
    accepted, quarantined = int(counts["accepted"]), int(counts["quarantined"])
    rules = {r["rule_id"]: int(r["quarantined_rows"]) for r in data.get("reglas", []) if int(r["year"]) == year}
    return CalidadMes(mes=Month(year, month.month).label, rows_read=accepted + quarantined, rows_accepted=accepted,
                      rows_quarantined=quarantined, rows_with_warnings=None, reconciled=True, rules=rules,
                      source="warehouse")


def rule_descriptions() -> dict[str, str]:
    """Spanish description of each quality rule (`descripcion` in contracts/quality_rules.yaml)."""
    import yaml

    from src.calidad import RULES_PATH

    spec = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")) or {}
    return {r["id"]: str(r.get("descripcion") or r.get("description") or "").strip() for r in spec.get("rules", [])}


def _que(text: str) -> str:
    """Description as part of a sentence: first letter lower-case, no final period."""
    text = text.strip().rstrip(".")
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def zone_name(location_id: int, name: str | None) -> str:
    """The lookup has no name for 264 (N/A, "Unknown") and for some legacy ids: they are named by their id."""
    if name and name.strip() and name.strip().upper() != "N/A":
        return name.strip()
    return {264: "zona desconocida (264)", 265: "fuera de NYC (265)"}.get(location_id, f"zona {location_id}")


# --- análisis ----------------------------------------------------------------------------------------------------
class Analisis:
    """Every fact the texts use, computed once from the query results."""

    def __init__(self, settings: Settings, month: Month, data: dict[str, list[dict[str, Any]]],
                 questions: list[dict[str, Any]], quality: dict[int, CalidadMes | None] | None = None):
        from src.calidad import load_rules

        self.settings, self.month = settings, month
        self.A, self.B = month.year, month.comparison.year
        self.mes_a, self.mes_b = mes_es(month), mes_es(month.comparison)
        self.data = data
        self.q = {r["index"]: r for r in questions}
        self.params, rules = load_rules()
        self.rules = {r.id: r for r in rules}
        self.descripcion = rule_descriptions()
        self.perfil = {int(r["year"]): r for r in data.get("perfil_mes", [])}
        self.ok = self.A in self.perfil and self.B in self.perfil
        self.quality: dict[int, CalidadMes | None] = dict(quality or {})
        for year in (self.A, self.B):
            stored = self.quality.get(year)
            warehouse = quality_from_warehouse(month, year, data)
            if stored is None or (warehouse is not None and stored.rows_accepted != warehouse.rows_accepted):
                # No local report, or one from another run than the rows in the warehouse: the warehouse wins.
                if stored is not None and warehouse is not None:
                    warehouse.schema, warehouse.ingestion = stored.schema, stored.ingestion
                self.quality[year] = warehouse
        self._zones()
        self._hours()
        self.dias = {y: {int(r["day_of_week_iso"]): r for r in data.get("dias_semana", []) if int(r["year"]) == y}
                     for y in (self.A, self.B)}
        self.cbd_daily = {y: sorted((r for r in data.get("cbd_diario", []) if int(r["year"]) == y),
                                    key=lambda r: r["pickup_date"]) for y in (self.A, self.B)}
        self.pagos = {y: {int(r["payment_type"]): r for r in data.get("pagos", [])
                          if int(r["year"]) == y and r["payment_type"] is not None} for y in (self.A, self.B)}
        self.aero = {int(r["year"]): r for r in data.get("aeropuertos", [])}
        self.atipicos = {y: sorted((r for r in data.get("atipicos", []) if int(r["year"]) == y),
                                   key=lambda r: r["rank_in_month"]) for y in (self.A, self.B)}

    # -- helpers over the data
    def p(self, year: int, key: str, default: float = 0.0) -> float:
        value = self.perfil.get(year, {}).get(key)
        return default if value is None else float(value)

    def _zones(self) -> None:
        zones: dict[int, dict[str, Any]] = {}
        for r in self.data.get("zonas", []):
            location = int(r["pu_location_id"])
            entry = zones.setdefault(location, {"id": location, "zone": zone_name(location, r["zone"]),
                                                "borough": r["borough"] or "Unknown", self.A: 0, self.B: 0})
            entry[int(r["year"])] += int(r["trips"])
        self.zones = zones
        self.zone_total = {y: sum(z[y] for z in zones.values()) for y in (self.A, self.B)}
        self.top = {y: sorted((z for z in zones.values() if z[y] > 0), key=lambda z: -z[y])[:10] for y in (self.A, self.B)}
        boroughs: dict[str, dict[int, int]] = {}
        for z in zones.values():
            name = z["borough"] or "Unknown"
            b = boroughs.setdefault(name, {self.A: 0, self.B: 0})
            b[self.A] += z[self.A]
            b[self.B] += z[self.B]
        self.boroughs = boroughs

    def zone_by_name(self, name: str) -> dict[str, Any] | None:
        return next((z for z in self.zones.values() if z["zone"] == name), None)

    def _hours(self) -> None:
        self.hours: dict[int, dict[int, dict[str, Any]]] = {self.A: {}, self.B: {}}
        for r in self.data.get("horas", []):
            year = int(r["year"])
            if year in self.hours:
                self.hours[year][int(r["pickup_hour"])] = r

    def has_outliers(self) -> bool:
        return bool(self.p(self.A, "fares_over_cap") + self.p(self.B, "fares_over_cap"))

    def fare(self, year: int, key: str = "avg_fare") -> float:
        """Average fare without fares above FARE_CAP when some month has them, else the plain average."""
        if self.has_outliers():
            return self.p(year, f"{key}_capped", self.p(year, key))
        return self.p(year, key)

    def trips(self, year: int) -> int:
        return int(self.p(year, "trips"))

    def airport_share(self, year: int) -> float:
        return share(self.aero.get(year, {}).get("airport_trips"), self.trips(year))

    def flex_share(self, year: int) -> float:
        return share(self.p(year, "flex_trips"), self.trips(year))

    def rule_pct(self, year: int, rule: str) -> float | None:
        quality = self.quality.get(year)
        if quality is None or rule not in quality.rules:
            return None
        return quality.pct(quality.rules[rule])

    def cbd_start(self) -> date | None:
        value = str(self.params.get("cbd_fee_start", "")).strip()
        try:
            return datetime.fromisoformat(value).date() if value else None
        except ValueError:
            return None

    def biggest_outlier(self) -> dict[str, Any] | None:
        candidates = [r for y in (self.A, self.B) for r in self.atipicos[y]]
        return max(candidates, key=lambda r: r["fare_amount"]) if candidates else None

    def outlier_text(self, row: dict[str, Any]) -> str:
        route = f"de {row['pu_zone']} a {row['do_zone']}" if row.get("pu_zone") and row.get("do_zone") else ""
        details = [route, f"{decimal(float(row['trip_distance']), 1)} millas" if row.get("trip_distance") is not None else "",
                   f"pago {PAGOS.get(int(row['payment_type']), 'desconocido')}" if row.get("payment_type") is not None else ""]
        details = [d for d in details if d]
        return f"fare_amount = {usd(float(row['fare_amount']))}" + (f" ({', '.join(details)})" if details else "")


# --- secciones -----------------------------------------------------------------------------------------------
def resumen(a: Analisis) -> str:
    if not a.ok:
        return (f"No hay viajes aceptados para comparar {a.mes_a} con {a.mes_b}: revisá la sección de calidad, que "
                "explica qué pasó con las filas de cada archivo.")
    trips_change = variacion(a.trips(a.A), a.trips(a.B))
    revenue_change = variacion(a.p(a.A, "revenue"), a.p(a.B, "revenue"))
    move = verbo(trips_change, "más", "menos", "casi los mismos")
    text = (f"En {a.mes_a} los taxis amarillos hicieron {entero(a.trips(a.A))} viajes válidos, "
            f"{signo(trips_change) + ' ' if trips_change is not None and move != 'casi los mismos' else ''}"
            f"{'que' if move != 'casi los mismos' else 'viajes que'} en {a.mes_b} ({entero(a.trips(a.B))}), "
            f"con una recaudación de {usd_millones(a.p(a.A, 'revenue'))} ({signo(revenue_change)}).")
    if move == "casi los mismos":
        text = (f"En {a.mes_a} los taxis amarillos hicieron {entero(a.trips(a.A))} viajes válidos, casi los mismos que en "
                f"{a.mes_b} ({entero(a.trips(a.B))}), con una recaudación de {usd_millones(a.p(a.A, 'revenue'))} "
                f"({signo(revenue_change)}).")
    return text


def calidad_seccion(a: Analisis) -> list[str]:
    """Markdown lines: how the quality gate works, both months side by side, every rule, the schema."""
    cloud = a.settings.warehouse == "snowflake"
    lines = [
        "Antes de responder las preguntas, cada archivo parquet de la TLC pasa por el contrato de esquema "
        "(`contracts/yellow_schema.yaml`) y por las reglas de calidad (`contracts/quality_rules.yaml`). "
        "Cada fila leída termina en un solo lugar: **aceptada** (capa curated, y de ahí al warehouse y a los marts) "
        f"o **en cuarentena** (`<DATA_DIR>/quarantine/yellow/year={a.A}/month={a.month.month:02d}/` y el mismo camino para "
        f"{a.B}, la tabla "
        f"`{'RAW.YELLOW_QUARANTINE' if cloud else 'raw.yellow_quarantine'}`"
        f"{', además de una copia en `s3://<bucket>/quarantine/yellow/`' if cloud else ''}). "
        "Una fila en cuarentena conserva sus valores originales, el archivo y el número de fila de origen "
        "(`source_file`, `source_row_number`) y las reglas de rechazo que violó (`violated_rules`). "
        "Las reglas `warning` no descartan la fila: solo la marcan en `quality_flags`. Si en algún mes "
        "`leídas = aceptadas + cuarentena` no se cumpliera, el pipeline se detiene antes de publicar ese mes.",
        "",
    ]
    qa, qb = a.quality.get(a.A), a.quality.get(a.B)
    months = [(a.month, qa), (a.month.comparison, qb)]
    lines += ["| mes | archivo | filas en el parquet | leídas | aceptadas | cuarentena | % cuarentena | aceptadas con warnings | reconcilia |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for month, q in months:
        if q is None:
            lines.append(f"| {month.label} | sin reporte de calidad |  |  |  |  |  |  |  |")
            continue
        file_name = Path(str(q.ingestion.get("file", ""))).name or f"yellow_tripdata_{month.label}.parquet"
        file_rows = q.ingestion.get("row_count")
        warnings = "-" if q.rows_with_warnings is None else f"{entero(q.rows_with_warnings)} ({pct(q.pct(q.rows_with_warnings), 2)})"
        lines.append(
            f"| {month.label} | `{file_name}` | {entero(file_rows) if file_rows is not None else '-'} | {entero(q.rows_read)} | "
            f"{entero(q.rows_accepted)} | {entero(q.rows_quarantined)} | {pct(q.pct(q.rows_quarantined), 2)} | "
            f"{warnings} | {'sí' if q.reconciled and q.rows_read == q.rows_accepted + q.rows_quarantined else 'no'} |")
    lines.append("")

    # every rule, both months
    lines += [f"| regla | severidad | qué controla | {a.month.label} | {a.month.comparison.label} | cambio |",
              "|---|---|---|---:|---:|---:|"]
    for rule in a.rules.values():
        cells = []
        values = []
        for _, q in months:
            if q is None or (rule.id not in q.rules and q.source == "warehouse" and rule.severity == "warning"):
                cells.append("-")
                values.append(None)
                continue
            rows = q.rules.get(rule.id, 0)
            values.append(q.pct(rows))
            cells.append(f"{entero(rows)} ({pct(q.pct(rows), 2)})")
        change = puntos(values[0] - values[1], 2) if None not in values else "-"
        lines.append(f"| {rule.id} | {rule.severity} | {a.descripcion.get(rule.id) or rule.description} | {cells[0]} | "
                     f"{cells[1]} | {change} |")
    lines += ["", "Una fila puede violar varias reglas, por eso la suma por regla supera el total en cuarentena.", ""]
    lines += [f"- {p}" for p in calidad_lectura(a)]
    lines.append("")
    lines += [f"- {p}" for p in esquema_lectura(a)]
    return lines


def calidad_lectura(a: Analisis) -> list[str]:
    """Plain-language reading of the quarantine: size, what drives it, what changed."""
    out: list[str] = []
    qa, qb = a.quality.get(a.A), a.quality.get(a.B)
    if qa is None or qb is None:
        missing = [m.label for m, q in ((a.month, qa), (a.month.comparison, qb)) if q is None]
        out.append(f"No hay reporte de calidad para {lista(missing)} en la base de control ni en el warehouse: "
                   "corré `make all` para ese mes.")
        return out
    pa, pb = qa.pct(qa.rows_quarantined), qb.pct(qb.rows_quarantined)
    trend = verbo(pa - pb, "sube", "baja", "se mantiene", stable=0.1)
    text = (f"La cuarentena {trend} {'en' if trend == 'se mantiene' else 'del'} "
            f"{pct(pb, 2) + ' al ' + pct(pa, 2) if trend != 'se mantiene' else pct(pa, 2) + ' (' + pct(pb, 2) + ' en ' + a.mes_b + ')'} "
            f"de las filas leídas ({entero(qa.rows_quarantined)} filas en {a.mes_a} y {entero(qb.rows_quarantined)} en {a.mes_b}).")
    rejects = [r for r in a.rules.values() if r.severity == "reject"]
    ranked = sorted(rejects, key=lambda r: -qa.rules.get(r.id, 0))
    drivers = [r for r in ranked if qa.rules.get(r.id, 0) > 0][:2]
    if drivers:
        parts = [f"{r.id} ({_que(a.descripcion.get(r.id) or r.description)}: {pct(qa.pct(qa.rules.get(r.id, 0)), 2)} "
                 f"contra {pct(qb.pct(qb.rules.get(r.id, 0)), 2)})" for r in drivers]
        text += f" La explican sobre todo {lista(parts)}."
    out.append(text)
    moved = sorted(rejects, key=lambda r: -abs(qa.pct(qa.rules.get(r.id, 0)) - qb.pct(qb.rules.get(r.id, 0))))
    if moved:
        r = moved[0]
        delta = qa.pct(qa.rules.get(r.id, 0)) - qb.pct(qb.rules.get(r.id, 0))
        if abs(delta) >= 0.1 and r not in drivers:
            out.append(f"La regla que más cambia es {r.id} ({_que(a.descripcion.get(r.id) or r.description)}): "
                       f"{puntos(delta, 2)} de las filas leídas.")
    warnings = [r for r in a.rules.values() if r.severity == "warning"]
    if qa.rows_with_warnings is not None and warnings:
        main = max(warnings, key=lambda r: qa.rules.get(r.id, 0))
        if qa.rules.get(main.id, 0):
            out.append(
                f"Las reglas de advertencia no sacan filas: {entero(qa.rows_with_warnings)} filas aceptadas de {a.mes_a} "
                f"({pct(qa.pct(qa.rows_with_warnings), 1)}) llevan alguna marca, la más común {main.id} "
                f"({_que(a.descripcion.get(main.id) or main.description)}: {pct(qa.pct(qa.rules.get(main.id, 0)), 1)}, "
                f"contra {pct(qb.pct(qb.rules.get(main.id, 0)), 1)} en {a.mes_b}).")
    reconciled = all(q.reconciled and q.rows_read == q.rows_accepted + q.rows_quarantined for q in (qa, qb))
    out.append("En los dos meses se cumple la reconciliación: leídas = aceptadas + cuarentena." if reconciled else
               "La reconciliación NO se cumple en algún mes: el pipeline no debería haber publicado ese mes.")
    if qa.source == "warehouse" or qb.source == "warehouse":
        out.append("La base de control local no tenía el reporte completo de algún mes, así que los conteos salen del "
                   "warehouse (aceptadas en fact_trips, cuarentena en raw.yellow_quarantine) y no incluyen las advertencias.")
    return out


def esquema_lectura(a: Analisis) -> list[str]:
    """What each parquet brought compared with the contract, and what the pipeline did about it."""
    out: list[str] = []
    for month, q in ((a.month, a.quality.get(a.A)), (a.month.comparison, a.quality.get(a.B))):
        name = mes_es(month)
        schema = (q.schema if q else {}) or {}
        if not schema:
            out.append(f"Esquema de {name}: sin reporte en la base de control (los datos vienen del warehouse).")
            continue
        notes: list[str] = []
        derived = (schema.get("derived") or {}).get("inputs") or {}
        if derived:
            unresolved = (schema.get("derived") or {}).get("unresolved") or {}
            lost = sum(v.get("unknown_264", 0) for v in unresolved.values())
            outside = sum(v.get("outside_nyc_265", 0) for v in unresolved.values())
            notes.append(
                "tiene el formato anterior a 2011: no trae ids de zona sino coordenadas "
                f"({lista(sorted({c for cols in derived.values() for c in cols}))}), así que la zona de origen y destino "
                "se obtuvo ubicando cada punto dentro de los polígonos oficiales de la TLC"
                + (f" ({entero(lost)} extremos sin coordenada quedaron en la zona 264 Unknown y {entero(outside)} fuera de "
                   "toda zona en la 265 Outside of NYC)" if lost or outside else ""))
        if schema.get("value_mapped"):
            notes.append(f"trae códigos de texto en {lista([f'`{c}`' for c in schema['value_mapped']])} (por ejemplo CASH o "
                         "Credit), traducidos a los códigos numéricos actuales")
        missing = schema.get("missing_optional") or []
        if missing:
            explained = [f"`{c}`" for c in missing]
            reason = (" (el peaje de congestión todavía no existía)" if "cbd_congestion_fee" in missing and len(missing) == 1
                      else " (columnas que todavía no existían)")
            notes.append(f"no trae {lista(explained)}{reason}: {'queda' if len(missing) == 1 else 'quedan'} en NULL, no en 0, para no confundir "
                         "\"no se cobró\" con \"no existía\"")
        if schema.get("new_columns"):
            notes.append(f"trae columnas nuevas que el contrato no conoce ({lista([f'`{c}`' for c in schema['new_columns']])}): "
                         "se ignoran y se reportan, sin romper la carga")
        mismatches = schema.get("type_mismatches") or {}
        if mismatches:
            shown = [f"`{c}` ({t.replace(' -> ', ' → ')})" for c, t in list(mismatches.items())[:4]]
            more = f" y {len(mismatches) - 4} más" if len(mismatches) > 4 else ""
            notes.append(f"guarda algunos campos con otro tipo ({', '.join(shown)}{more}): se convierten con TRY_CAST")
        failures = schema.get("cast_failures") or {}
        if failures:
            notes.append(f"{entero(sum(failures.values()))} valores no se pudieron convertir y quedaron en NULL "
                         f"({', '.join(f'`{c}`: {entero(n)}' for c, n in failures.items())}); las reglas de calidad "
                         "deciden qué pasa con esas filas")
        nulls = {c: n for c, n in (schema.get("null_violations") or {}).items() if c not in failures}
        if nulls:
            notes.append(f"tiene NULL en columnas obligatorias ({', '.join(f'`{c}`: {entero(n)}' for c, n in nulls.items())})")
        if notes:
            out.append(f"Esquema de {name}: el archivo {lista(notes)}.")
        else:
            out.append(f"Esquema de {name}: el archivo coincide con el contrato (mismas columnas y tipos).")
    return out


def q1(a: Analisis) -> str:
    A, B = a.A, a.B
    top = a.top[A]
    if not top:
        return f"No hay pickups aceptados en {a.mes_a}."
    n = len(top)
    manh = sum(1 for z in top if z["borough"] == "Manhattan")
    lead = (f"Las {numero(n)} zonas con más pickups están en Manhattan" if manh == n else
            f"Ninguna de las {numero(n)} zonas con más pickups está en Manhattan" if manh == 0 else
            f"{cap(numero(manh))} de las {numero(n)} zonas con más pickups {'está' if manh == 1 else 'están'} en Manhattan")
    changes = [(z, variacion(z[A], z[B])) for z in top]
    known = [(z, c) for z, c in changes if c is not None]
    up = [(z, c) for z, c in known if c >= STABLE_PCT]
    down = [(z, c) for z, c in known if c <= -STABLE_PCT]
    sentences = []
    every = "todas" if manh == n else f"las {numero(n)}"  # "todas" only when it cannot mean "the Manhattan ones"
    if known and len(up) == len(known):
        lo, hi = min(up, key=lambda x: x[1]), max(up, key=lambda x: x[1])
        lead += (f" y {every} crecen alrededor de {signo(hi[1])}" if hi[1] - lo[1] < 1 else
                 f" y {every} crecen, entre {signo(lo[1])} ({lo[0]['zone']}) y {signo(hi[1])} ({hi[0]['zone']})")
    elif known and len(down) == len(known):
        lo, hi = min(down, key=lambda x: x[1]), max(down, key=lambda x: x[1])
        lead += (f" y {every} caen alrededor de {signo(lo[1])}" if hi[1] - lo[1] < 1 else
                 f" y {every} caen, entre {signo(hi[1])} ({hi[0]['zone']}) y {signo(lo[1])} ({lo[0]['zone']})")
    elif known:
        parts = []
        if up:
            lo, hi = min(up, key=lambda x: x[1]), max(up, key=lambda x: x[1])
            span = (f"entre {signo(lo[1])} en {lo[0]['zone']} y {signo(hi[1])} en {hi[0]['zone']}" if len(up) > 1 else
                    f"{signo(hi[1])} en {hi[0]['zone']}")
            parts.append(f"{numero(len(up))} crece{'n' if len(up) > 1 else ''} ({span})")
        if down and len(down) > 3:
            lo, hi = min(down, key=lambda x: x[1]), max(down, key=lambda x: x[1])
            parts.append(f"{numero(len(down))} caen (entre {signo(hi[1])} en {hi[0]['zone']} y {signo(lo[1])} en "
                         f"{lo[0]['zone']})")
        elif down:
            parts.append(f"{numero(len(down))} cae{'n' if len(down) > 1 else ''} "
                         f"({', '.join(z['zone'] + ' ' + signo(c) for z, c in sorted(down, key=lambda x: x[1]))})")
        flat = len(known) - len(up) - len(down)
        if flat:
            parts.append(f"{numero(flat)} se mantiene{'n' if flat > 1 else ''}")
        lead += f". Dentro del top 10, {lista(parts)}"
    sentences.append(lead + ".")
    new_zones = [z for z, c in changes if c is None]
    leader, leader_change = changes[0]
    text = f"{leader['zone']} lidera con {entero(leader[A])} viajes" + (f" ({signo(leader_change)})" if leader_change is not None else "")
    previous = a.top[B][0] if a.top[B] else None
    if previous and previous["id"] != leader["id"]:
        text += f" y desplaza a {previous['zone']}, que encabezaba {a.mes_b}"
    sentences.append(text + ".")
    if new_zones:
        sentences.append(f"{lista([z['zone'] for z in new_zones])} no tenía{'n' if len(new_zones) > 1 else ''} pickups en {a.mes_b}.")
    ins = [z for z in top if z["id"] not in {t["id"] for t in a.top[B]}]
    outs = [z for z in a.top[B] if z["id"] not in {t["id"] for t in top}]
    if ins and a.top[B]:
        sentences.append(f"Respecto de {a.mes_b} entra{'n' if len(ins) > 1 else ''} al top 10 {lista([z['zone'] for z in ins])} "
                         f"y sale{'n' if len(outs) > 1 else ''} {lista([z['zone'] for z in outs])}.")
    city = variacion(a.zone_total[A], a.zone_total[B])
    airports = [(name, a.zone_by_name(name)) for name in AIRPORTS]
    airports = [(name, z, variacion(z[A], z[B])) for name, z in airports if z and z[B] > 0]
    if airports and city is not None:
        parts = []
        for name, z, c in airports:
            rank = next((i for i, t in enumerate(top, start=1) if t["id"] == z["id"]), None)
            where = f"puesto {rank} del top" if rank else "fuera del top"
            parts.append(f"{name.replace(' Airport', '')} ({where}) {verbo(c, 'crece', 'cae')} {signo(c)}")
        gap = [c - city for _, _, c in airports]
        if all(g <= -3 for g in gap):
            growing = [c >= 3 for _, _, c in airports]  # growing for real, not just a fraction of a percent
            if city > STABLE_PCT and not any(growing):
                reading = f": el crecimiento de {A} es de viajes urbanos, no de aeropuertos"
            elif city > STABLE_PCT and all(growing):
                reading = f": crecen, pero menos que el total de la ciudad ({signo(city)})"
            elif city > STABLE_PCT:
                reading = f": los dos quedan por debajo del total de la ciudad ({signo(city)})"
            else:
                reading = f": los aeropuertos van peor que el total de la ciudad ({signo(city)})"
        elif all(g >= 3 for g in gap):
            reading = f": los aeropuertos van mejor que el total de la ciudad ({signo(city)})"
        elif all(abs(g) < 3 for g in gap):
            reading = f", en línea con el total de la ciudad ({signo(city)})"
        else:
            groups = {"peor": [], "mejor": [], "en línea con él": []}
            for (name, _, _), g in zip(airports, gap):
                groups["peor" if g <= -3 else "mejor" if g >= 3 else "en línea con él"].append(name.replace(" Airport", ""))
            said = [f"{lista(names)} {'va' if len(names) == 1 else 'van'} {how}" if how != "en línea con él" else
                    f"{lista(names)} {'queda' if len(names) == 1 else 'quedan'} en línea con él"
                    for how, names in groups.items() if names]
            said[0] = said[0].replace(" va peor", " va peor que el total de la ciudad", 1).replace(
                " va mejor", " va mejor que el total de la ciudad", 1).replace(" van peor", " van peor que el total de la ciudad", 1).replace(
                " van mejor", " van mejor que el total de la ciudad", 1)
            reading = f": {lista(said)} ({signo(city)})"
        sentences.append(f"En los aeropuertos, {lista(parts)}{reading}.")
    share_a = share(sum(z[A] for z in top), a.zone_total[A])
    share_b = share(sum(z[B] for z in a.top[B]), a.zone_total[B])
    if a.top[B]:
        if share_a - share_b <= -0.5:
            sentences.append(f"La demanda además se reparte más: el top 10 concentra el {pct(share_a)} de los pickups, "
                             f"frente al {pct(share_b)} de {B}.")
        elif share_a - share_b >= 0.5:
            sentences.append(f"La demanda se concentra más: el top 10 reúne el {pct(share_a)} de los pickups, "
                             f"frente al {pct(share_b)} de {B}.")
        else:
            sentences.append(f"La concentración casi no cambia: el top 10 reúne el {pct(share_a)} de los pickups "
                             f"({pct(share_b)} en {B}).")
    borough = _borough_story(a, city)
    if borough:
        sentences.append(borough)
    return " ".join(sentences)


def _borough_story(a: Analisis, city: float | None) -> str:
    if city is None:
        return ""
    candidates = []
    for name, values in a.boroughs.items():
        if name in {"Manhattan", "Unknown", "N/A"} or values[a.B] <= 0:
            continue
        weight = max(share(values[a.A], a.zone_total[a.A]), share(values[a.B], a.zone_total[a.B]))
        change = variacion(values[a.A], values[a.B])
        if weight >= 0.5 and change is not None and abs(change - city) >= 10:
            candidates.append((abs(change - city), name, values, change, weight))
    if not candidates:
        return ""
    _, name, values, change, weight = max(candidates)
    ratio = values[a.A] / values[a.B]
    if ratio >= 3:
        move = "más que triplica"
    elif ratio >= 2.5:
        move = "casi triplica"
    elif ratio >= 1.9:
        move = "duplica"
    elif ratio <= 0.5:
        move = "pierde más de la mitad de"
    else:
        move = f"{verbo(change, 'crece', 'cae')} {signo(change)} en"
    base = ", aunque sobre una base chica" if weight < 3 else ""
    name = {"Bronx": "el Bronx", "EWR": "Newark (EWR)"}.get(name, name)
    return (f"Fuera de Manhattan, {name} {move} sus pickups ({entero(values[a.B])} → {entero(values[a.A])}){base}, "
            f"contra {signo(city)} del total.")


def q2(a: Analisis) -> str:
    rows = {int(r["year"]): r for r in a.q[2]["records"]}
    if a.A not in rows:
        return f"No hay viajes aceptados en {a.mes_a}."
    ha, ra = int(rows[a.A]["pickup_hour"]), float(rows[a.A]["avg_revenue_per_trip"])
    sentences = []
    if a.B in rows:
        hb, rb = int(rows[a.B]["pickup_hour"]), float(rows[a.B]["avg_revenue_per_trip"])
        if ha == hb:
            sentences.append(f"La hora con mayor ingreso promedio por viaje es {hora(ha)} en los dos años: "
                             f"{usd(ra)} en {a.A} y {usd(rb)} en {a.B}.")
        else:
            sentences.append(f"La hora con mayor ingreso promedio por viaje cambia: {hora(ha)} en {a.A} ({usd(ra)}) "
                             f"y {hora(hb)} en {a.B} ({usd(rb)}).")
    else:
        hb, rb = None, None
        sentences.append(f"La hora con mayor ingreso promedio por viaje de {a.mes_a} es {hora(ha)} ({usd(ra)}).")
    hours_a = a.hours[a.A]
    if ha in hours_a:
        row = hours_a[ha]
        peak_a = max(hours_a.values(), key=lambda r: r["trips"])
        peak_b = max(a.hours[a.B].values(), key=lambda r: r["trips"]) if a.hours[a.B] else None
        same_peak = peak_b is not None and int(peak_b["pickup_hour"]) == int(peak_a["pickup_hour"])
        if row["trips"] < 0.5 * peak_a["trips"]:
            sentences.append(f"Es una hora de poco volumen ({entero(row['trips'])} viajes, contra {entero(peak_a['trips'])} a "
                             f"{hora(peak_a['pickup_hour'])}, la hora pico de demanda{' en ambos años' if same_peak else ''}).")
        else:
            sentences.append(f"Además es una hora de mucho movimiento ({entero(row['trips'])} viajes; la hora pico es "
                             f"{hora(peak_a['pickup_hour'])} con {entero(peak_a['trips'])}).")
        total_trips = sum(r["trips"] for r in hours_a.values())
        airport_all = share(sum(r["airport_trips"] for r in hours_a.values()), total_trips)
        airport_h = share(row["airport_trips"], row["trips"])
        dist_all = sum(float(r["avg_distance"] or 0) * r["trips"] for r in hours_a.values()) / total_trips
        dist_h = float(row["avg_distance"] or 0)
        reasons = []
        if airport_h >= 1.3 * airport_all and airport_h - airport_all >= 2:
            reasons.append(f"el {pct(airport_h)} de sus viajes toca JFK o LaGuardia (contra {pct(airport_all)} en todo el mes)")
        if dist_h >= 1.2 * dist_all:
            reasons.append(f"la distancia media es de {decimal(dist_h)} millas (contra {decimal(dist_all)})")
        artificial = bool(_hour_outlier(a, a.A)) and _hour_outlier(a, a.A).startswith("Ojo con el primer")
        if reasons:
            sentences.append(f"Gana porque a esa hora pesan los viajes largos: {lista(reasons)}.")
        elif not artificial:
            sentences.append("No la explican los aeropuertos ni la distancia, que a esa hora son parecidos al resto del "
                             "día: pesan los recargos y peajes de esos viajes.")
        if hb == ha and ha in a.hours[a.B]:
            row_b = a.hours[a.B][ha]
            change = variacion(ra, rb)
            airport_hb = share(row_b["airport_trips"], row_b["trips"])
            dist_hb = float(row_b["avg_distance"] or 0)
            # (text, sign): a cause raises (+1) or lowers (-1) the revenue per trip
            causes: list[tuple[str, int]] = []
            if abs(airport_h - airport_hb) >= 1:
                causes.append((f"los viajes de aeropuerto son {'más' if airport_h > airport_hb else 'menos'} (del "
                               f"{pct(airport_hb)} al {pct(airport_h)} de los viajes de {hora(ha)})",
                               1 if airport_h > airport_hb else -1))
            dist_change = variacion(dist_h, dist_hb)
            if dist_change is not None and abs(dist_change) >= 3:
                causes.append((f"la distancia media {verbo(dist_change)} (de {decimal(dist_hb)} a {decimal(dist_h)} millas)",
                               1 if dist_change > 0 else -1))
            if change is not None and abs(change) >= 1:
                direction = 1 if change > 0 else -1
                along = [t for t, sign in causes if sign == direction]
                against = [t for t, sign in causes if sign != direction]
                move = f"{verbo(change, 'sube', 'cae')} un {pct(abs(change))}"
                if along:
                    sentences.append(f"En {a.A} {lista(along)}, por eso el ingreso por viaje {move}"
                                     + (f", aunque {lista(against)}." if against else "."))
                elif against:
                    sentences.append(f"El ingreso por viaje de esa hora {move} aunque {lista(against)}: lo explican las "
                                     f"tarifas y recargos de {a.A}.")
                else:
                    sentences.append(f"El ingreso por viaje de esa hora {move} con un perfil de viaje parecido: pesan "
                                     f"las tarifas y recargos de {a.A}.")
    for year in (a.A, a.B):
        warning = _hour_outlier(a, year)
        if warning:
            sentences.append(warning)
    return " ".join(sentences)


def _hour_outlier(a: Analisis, year: int) -> str:
    """Warns when one of the top-3 hours is there only because of a fare above FARE_CAP."""
    hours = a.hours[year]
    if not hours:
        return ""
    raw = sorted(hours.values(), key=lambda r: -float(r["revenue_per_trip"]))
    robust = sorted(hours.values(), key=lambda r: -float(r["revenue_per_trip_capped"] or 0))
    robust_rank = {int(r["pickup_hour"]): i for i, r in enumerate(robust, start=1)}
    for rank, row in enumerate(raw[:3], start=1):
        hour, max_fare = int(row["pickup_hour"]), float(row["max_fare"] or 0)
        capped = float(row["revenue_per_trip_capped"] or 0)
        value = float(row["revenue_per_trip"])
        if max_fare > FARE_CAP and robust_rank[hour] > rank and value - capped >= 0.03 * value:
            return (f"Ojo con el {ORDINALES[rank]} puesto de {year} ({hora(hour)}, {usd(value)}): es artificial, porque lo "
                    f"infla un viaje con una tarifa de {usd(max_fare)}. Sin las tarifas mayores a US$ {FARE_CAP}, "
                    f"esa hora queda en {usd(capped)}.")
    return ""


def q3(a: Analisis) -> str:
    records = a.q[3]["records"]
    overall = next((r for r in records if r["scope"] == "ALL ZONES"), None)
    reported = a.p(a.A, "cbd_fee_reported")
    start = a.cbd_start()
    start_text = f"{start.day} de {MESES[start.month - 1]} de {start.year}" if start else "enero de 2025"
    if not overall or not a.ok:
        return f"No hay viajes aceptados en {a.mes_a}."
    if reported == 0:
        return (f"En {a.mes_a} el peaje de congestión de Manhattan (cbd_congestion_fee) todavía no existía: el archivo "
                f"no trae la columna y queda en NULL (no en 0), así que el indicador vale 0 % por construcción y el ranking "
                f"de zonas no tiene significado. El cobro por viaje empezó el {start_text}; comparar contra un mes desde "
                "2025 muestra su efecto.")
    with_fee, trips = int(overall["trips_with_cbd_fee"]), int(overall["trips"])
    share_a = float(overall["pct_with_cbd_fee"])
    avg_fee, min_fee = a.p(a.A, "avg_cbd_fee"), a.p(a.A, "min_cbd_fee")
    amount = (f"siempre {usd(avg_fee)}" if abs(avg_fee - min_fee) < 0.005 else f"un cobro medio de {usd(avg_fee)}")
    sentences = [f"El {pct(share_a, 2)} de los viajes de {a.mes_a} pagó cbd_congestion_fee ({entero(with_fee)} de "
                 f"{entero(trips)}, {amount})."]
    daily = a.cbd_daily[a.A]
    if start and start.year == a.A and start.month == a.month.month and daily:
        before = [r for r in daily if r["pickup_date"] < start]
        after = [r for r in daily if r["pickup_date"] >= start]
        if before and after:
            trips_before = sum(r["trips"] for r in before)
            share_before = share(sum(r["trips_with_cbd_fee"] for r in before), trips_before)
            share_after = share(sum(r["trips_with_cbd_fee"] for r in after), sum(r["trips"] for r in after))
            r10 = a.quality.get(a.A).rules.get("R10") if a.quality.get(a.A) else None
            sentences.append(
                f"El porcentaje está diluido porque el peaje empezó el {start.day} de {MESES[start.month - 1]}: del 1 al "
                f"{start.day - 1} ({pct(share(trips_before, trips))} de los viajes del mes) casi nadie lo pagó "
                f"({pct(share_before, 2)}{'; esos cobros anticipados quedan marcados por la regla R10' if r10 else ''}), "
                f"y desde el {start.day} lo paga el {pct(share_after)}.")
    zones = [r for r in records if r["scope"] != "ALL ZONES"]
    if zones:
        names = [r["scope"] for r in zones]
        low, high = min(float(r["pct_with_cbd_fee"]) for r in zones), max(float(r["pct_with_cbd_fee"]) for r in zones)
        boroughs = {r["borough"] for r in zones}
        where = ("están todas en Manhattan, dentro de la zona de peaje" if boroughs == {"Manhattan"} else
                 f"están en {lista(sorted(b for b in boroughs if b))}")
        sentences.append(f"Las {numero(len(zones))} zonas con mayor proporción ({lista(names)}, "
                         f"{'alrededor del ' + pct(low, 0) if high - low < 2 else 'entre ' + pct(low) + ' y ' + pct(high)}) {where}.")
    reported_b = a.p(a.B, "cbd_fee_reported")
    if reported_b > 0:
        share_b = share(a.p(a.B, "trips_with_cbd_fee"), a.trips(a.B))
        diluted = bool(start and start.year == a.B and start.month == a.month.month)
        sentences.append(f"En {a.mes_b} lo pagaba el {pct(share_b, 2)} de los viajes"
                         + (f" (un mes diluido: el peaje empezó el {start.day} de {MESES[start.month - 1]})" if diluted else "")
                         + f": la proporción {verbo(share_a - share_b, 'sube', 'baja', 'se mantiene', stable=0.2)} "
                         f"{puntos(share_a - share_b) if abs(share_a - share_b) >= 0.2 else ''}".rstrip() + ".")
    else:
        sentences.append(f"En {a.mes_b} la columna no existía y quedó en NULL (no en 0), así que este indicador no tiene "
                         "contra qué compararse.")
    quality = a.quality.get(a.A)
    anomalies = quality.rules.get("R10", 0) if quality else 0
    if anomalies:
        sentences.append(f"La regla R10 marcó {entero(anomalies)} filas con un cobro anómalo (negativo, es decir una "
                         "reversión, o anterior al inicio del peaje): se conservan con su marca.")
    return " ".join(sentences)


def q4(a: Analisis) -> str:
    pa, pb = a.pagos[a.A], a.pagos[a.B]
    sentences = []
    card_a, card_b = pa.get(1), pb.get(1)
    if card_a:
        tip_a, tip_b = float(card_a["avg_tip_pct"] or 0), float(card_b["avg_tip_pct"] or 0) if card_b else None
        w_a = float(card_a["weighted_tip_pct"] or 0)
        w_b = float(card_b["weighted_tip_pct"] or 0) if card_b else None
        with_tip_a = share(card_a["trips_with_tip"], card_a["trips_fare_positive"])
        if tip_b is not None:
            trend = verbo(tip_a - tip_b, "sube", "baja", "se mantiene estable", stable=0.3)
            sentences.append(
                f"Con tarjeta de crédito la propina {trend}: {pct(tip_a, 2)} de la tarifa en {a.A} frente a {pct(tip_b, 2)} "
                f"en {a.B} ({pct(w_a)} y {pct(w_b)} ponderada), y deja propina el {pct(with_tip_a, 0)} de esos viajes.")
        else:
            sentences.append(f"Con tarjeta de crédito la propina es el {pct(tip_a, 2)} de la tarifa ({pct(w_a)} ponderada).")
    cash = pa.get(2)
    if cash and float(cash["avg_tip_pct"] or 0) < 1:
        sentences.append("En efectivo da casi 0 % porque la TLC no registra las propinas en efectivo, no porque no se dejen.")
    flex_a, flex_b = pa.get(0), pb.get(0)
    share_a, share_b = a.flex_share(a.A), a.flex_share(a.B)
    if max(share_a, share_b) >= 0.5 and (flex_a or flex_b):
        tip_fa = float(flex_a["avg_tip_pct"] or 0) if flex_a else None
        tip_fb = float(flex_b["avg_tip_pct"] or 0) if flex_b else None
        big = abs(share_a - share_b) >= 2
        if share_b < 0.05:
            moved = f"aparece en {a.A} con el {pct(share_a, 1)}"
        elif share_a < 0.05:
            moved = f"desaparece en {a.A} (era el {pct(share_b, 1)})"
        elif abs(share_a - share_b) >= 0.2:
            moved = f"pasa del {pct(share_b, 1)} al {pct(share_a, 1)}"
        else:
            moved = f"se mantiene en el {pct(share_a, 1)}"
        text = (f"{'El cambio grande es' if big else 'También pesa'} Flex Fare (payment_type 0, tarifa fija acordada por app), "
                f"que {moved} de los viajes ({entero(flex_b['trips_fare_positive'] if flex_b else 0)} → "
                f"{entero(flex_a['trips_fare_positive'] if flex_a else 0)} con tarifa > 0)")
        if tip_fa is not None and tip_fb is not None:
            text += (f" y cuya propina se mantiene en torno al {pct(tip_fa, 1)}" if abs(tip_fa - tip_fb) < 0.3 else
                     f" y cuya propina {verbo(tip_fa - tip_fb, 'sube', 'cae', stable=0.3)} del {pct(tip_fb, 2)} al {pct(tip_fa, 2)}")
        sentences.append(text + ".")
        r05_a, r05_b = a.rule_pct(a.A, "R05"), a.rule_pct(a.B, "R05")
        if r05_a is not None and r05_b is not None and abs(r05_a - r05_b) >= 1:
            sentences.append(f"Esos viajes llegan sin passenger_count, y por eso las advertencias de la regla R05 "
                             f"{verbo(r05_a - r05_b, 'suben', 'bajan')} del {pct(r05_b)} al {pct(r05_a)} de las filas leídas.")
    card_share_a, card_share_b = share(a.p(a.A, "card_trips"), a.trips(a.A)), share(a.p(a.B, "card_trips"), a.trips(a.B))
    if abs(card_share_a - card_share_b) >= 2:
        sentences.append(f"La tarjeta {'gana' if card_share_a > card_share_b else 'pierde'} peso entre las formas de pago: "
                         f"del {pct(card_share_b)} al {pct(card_share_a)} de los viajes.")
    others = [pa.get(t) for t in (3, 4)]
    if all(o is not None and float(o["avg_tip_pct"] or 0) < 2 for o in others):
        sentences.append("\"No charge\" y \"Dispute\" tienen una propina cercana a 0, como es esperable.")
    return " ".join(sentences) or f"No hay pagos registrados en {a.mes_a}."


def q5(a: Analisis) -> str:
    ra, rb = a.aero.get(a.A), a.aero.get(a.B)
    if not ra or not rb:
        return "No hay viajes de aeropuerto en alguno de los dos meses."
    trips_change = variacion(ra["airport_trips"], rb["airport_trips"])
    city = variacion(a.trips(a.A), a.trips(a.B))
    share_a, share_b = a.airport_share(a.A), a.airport_share(a.B)
    sentences = [
        f"Los viajes que empiezan o terminan en JFK o LaGuardia {verbo(trips_change, 'suben', 'bajan', 'se mantienen')} "
        f"{'un ' + pct(abs(trips_change)) + ' ' if trips_change is not None and abs(trips_change) >= STABLE_PCT else ''}"
        f"({entero(rb['airport_trips'])} → {entero(ra['airport_trips'])}) mientras el total de la ciudad "
        f"{verbo(city, 'sube', 'baja', 'se mantiene')} {'un ' + pct(abs(city)) if city is not None and abs(city) >= STABLE_PCT else ''}"
        .rstrip() + (f", así que su peso se mantiene en el {pct(share_a)} de los viajes." if abs(share_a - share_b) < 0.1 else
                     f", así que su peso {verbo(share_a - share_b, 'sube', 'cae', stable=0.1)} del {pct(share_b)} al "
                     f"{pct(share_a)} de los viajes.")
    ]
    jfk, lga = variacion(ra["jfk_trips"], rb["jfk_trips"]), variacion(ra["lga_trips"], rb["lga_trips"])
    if jfk is not None and lga is not None:
        sentences.append(f"Por aeropuerto, JFK {verbo(jfk, 'crece', 'cae')} {signo(jfk)} y LaGuardia {verbo(lga, 'crece', 'cae')} {signo(lga)}.")
    fare_a, fare_b = float(ra["avg_fare"]), float(rb["avg_fare"])
    fare_change = variacion(fare_a, fare_b)
    capped_a, capped_b = float(ra["avg_fare_capped"] or fare_a), float(rb["avg_fare_capped"] or fare_b)
    capped_change = variacion(capped_a, capped_b)
    med_a, med_b = float(ra["median_fare"] or 0), float(rb["median_fare"] or 0)
    text = (f"La tarifa promedio se mantiene ({usd(fare_b)} → {usd(fare_a)})" if abs(fare_change or 0) < STABLE_PCT else
            f"La tarifa promedio {verbo(fare_change)} de {usd(fare_b)} a {usd(fare_a)} ({signo(fare_change)})")
    outlier = max((r for r in (ra, rb)), key=lambda r: float(r["max_fare"] or 0))
    distorted = (float(outlier["max_fare"] or 0) > FARE_CAP and fare_change is not None and capped_change is not None
                 and abs(fare_change - capped_change) >= 1)
    if distorted:
        year = int(outlier["year"])
        detail = next((r for r in a.atipicos[year] if abs(float(r["fare_amount"]) - float(outlier["max_fare"])) < 0.01), None)
        flips = (fare_change > 0) != (capped_change > 0)
        text += (f", pero esa {'suba' if fare_change > 0 else 'baja'} {'no es real' if flips else 'está exagerada'}: "
                 f"la produce un solo viaje de {year} con "
                 f"{a.outlier_text(detail) if detail else 'fare_amount = ' + usd(float(outlier['max_fare']))}.")
        text += (f" Excluyendo las tarifas mayores a US$ {FARE_CAP} en los dos años, el promedio pasa de {usd(capped_b)} a "
                 f"{usd(capped_a)} ({signo(capped_change)})")
    sentences.append(text + f", y la mediana {verbo(variacion(med_a, med_b))} de {usd(med_b)} a {usd(med_a)}."
                     if abs(variacion(med_a, med_b) or 0) >= STABLE_PCT else text + f", y la mediana se mantiene en {usd(med_a)}.")
    flat_a, flat_b = ra.get("jfk_flat_fare"), rb.get("jfk_flat_fare")
    if flat_a and flat_b:
        if abs(float(flat_a) - float(flat_b)) < 0.01:
            sentences.append(f"La tarifa fija de JFK (RatecodeID 2) sigue en {usd(float(flat_a))}.")
        else:
            sentences.append(f"La tarifa fija de JFK (RatecodeID 2) pasa de {usd(float(flat_b))} a {usd(float(flat_a))}.")
    if distorted:
        sentences.append("Ninguna regla de calidad pone un tope a la tarifa; ese hueco queda documentado como limitación.")
    return " ".join(sentences)


def q6(a: Analisis) -> str:
    if not a.ok:
        return f"No hay viajes aceptados en alguno de los dos meses ({a.mes_a}, {a.mes_b})."
    lines = []
    trips_a, trips_b = a.trips(a.A), a.trips(a.B)
    change = variacion(trips_a, trips_b) or 0.0
    revenue_change = variacion(a.p(a.A, "revenue"), a.p(a.B, "revenue")) or 0.0
    lines.append(
        f"{cap(a.mes_a)} tuvo {entero(trips_a)} viajes válidos contra {entero(trips_b)} en {a.mes_b}: "
        f"{signo(trips_a - trips_b, 0, '')} viajes ({signo(change, 2)}). La recaudación total (total_amount) "
        f"{verbo(revenue_change, 'crece', 'cae', 'se mantiene')} {'un ' + pct(abs(revenue_change)) + ', ' if abs(revenue_change) >= STABLE_PCT else ''}"
        f"de {usd_millones(a.p(a.B, 'revenue'))} a {usd_millones(a.p(a.A, 'revenue'))}.")
    lines.append(_calendar_line(a, change))
    lines.append(_fare_line(a))
    mix = _mix_line(a)
    if mix:
        lines.append(mix)
    lines.append(_quality_line(a))
    return "\n".join(line for line in lines if line)


def _calendar_line(a: Analisis, change: float) -> str:
    """Calendar effect: which weekdays appear 5 times in each month, and the change with the other calendar."""
    da, db = a.dias[a.A], a.dias[a.B]
    if not da or not db:
        return ""
    per_day = {y: {dow: (r["trips"] / r["days"] if r["days"] else 0) for dow, r in a.dias[y].items()} for y in (a.A, a.B)}
    days_a, days_b = sum(r["days"] for r in da.values()), sum(r["days"] for r in db.values())
    count_a = {dow: r["days"] for dow, r in da.items()}
    count_b = {dow: r["days"] for dow, r in db.items()}
    parts = []
    if count_a == count_b:
        parts.append("Los dos meses tienen la misma composición de días de la semana, así que no hay efecto calendario.")
    else:
        # weekdays the assigned month has more of, and the ones the comparison month has more of
        more_a = [d for d in sorted(count_a) if count_a[d] > count_b.get(d, 0)]
        more_b = [d for d in sorted(count_b) if count_b[d] > count_a.get(d, 0)]
        ranking = sorted(per_day[a.A], key=lambda d: -per_day[a.A][d])
        strong, weak = set(ranking[:3]), set(ranking[-3:])

        def describe(days: list[int], counts: dict[int, int]) -> str:
            if not days:
                return "ningún día de más"
            tone = "días fuertes" if set(days) <= strong else "días flojos" if set(days) <= weak else ""
            return lista([f"{counts[d]} {DIAS[d]}" for d in days]) + (f" ({tone})" if tone else "")

        adjusted = sum(per_day[a.A][dow] * db[dow]["days"] for dow in db if dow in per_day[a.A])
        adjusted_change = variacion(adjusted, a.trips(a.B))
        effect = change - adjusted_change if adjusted_change is not None else 0.0
        if more_a and more_b:
            composition = f"{a.mes_a} tuvo {describe(more_a, count_a)}, y {a.mes_b}, {describe(more_b, count_b)}"
        elif more_b:
            composition = f"{a.mes_b} tuvo {describe(more_b, count_b)} y {a.mes_a} no"
        else:
            composition = f"{a.mes_a} tuvo {describe(more_a, count_a)} y {a.mes_b} no"
        composition += f" ({days_a} contra {days_b} días)" if days_a != days_b else ""
        if abs(effect) < 0.3:
            lead = "El calendario casi no influye: "
        elif effect > 0 and change > 0:
            lead = "Parte del salto es de calendario: "
        elif effect < 0 and change < 0:
            lead = "Parte de la caída es de calendario: "
        elif effect > 0:
            lead = f"El calendario favorece a {a.mes_a}: "
        else:
            lead = f"El calendario juega en contra de {a.mes_a}: "
        parts.append(f"{lead}{composition}.")
        if adjusted_change is not None and abs(effect) >= 0.3:
            parts.append(f"Con el calendario de {a.B} la variación sería {signo(adjusted_change)}.")
    daily_changes = [variacion(per_day[a.A][d], per_day[a.B][d]) for d in per_day[a.A] if per_day[a.B].get(d)]
    daily_changes = [c for c in daily_changes if c is not None]
    if daily_changes:
        lo, hi = min(daily_changes), max(daily_changes)
        if lo > 0:
            parts.append(f"Todos los días de la semana crecen (por día), entre {signo(lo, 0)} y {signo(hi, 0)}, así que el "
                         "aumento es real.")
        elif hi < 0:
            parts.append(f"Todos los días de la semana caen (por día), entre {signo(hi, 0)} y {signo(lo, 0)}, así que la "
                         "baja es general.")
        else:
            parts.append(f"Por día de la semana la variación va de {signo(lo, 0)} a {signo(hi, 0)}: el cambio no es parejo.")
    for year, label in ((a.A, a.mes_a), (a.B, a.mes_b)):
        days = sum(r["days"] for r in a.dias[year].values())
        with_trips = int(a.p(year, "days_with_trips"))
        if 0 < with_trips < days:
            parts.append(f"Ojo: {label} tiene viajes solo en {with_trips} de sus {days} días.")
    return " ".join(parts)


def _fare_line(a: Analisis) -> str:
    fa, fb = a.p(a.A, "avg_fare"), a.p(a.B, "avg_fare")
    ca, cb = a.p(a.A, "avg_fare_capped", fa), a.p(a.B, "avg_fare_capped", fb)
    ma, mb = a.p(a.A, "median_fare"), a.p(a.B, "median_fare")
    change, capped, median = variacion(fa, fb), variacion(ca, cb), variacion(ma, mb)
    if change is None:
        return ""
    move = verbo(change)
    text = (f"La tarifa promedio {move} {'un ' + pct(abs(change), 2) + ' ' if move != 'se mantiene' else ''}"
            f"(de {usd(fb)} a {usd(fa)})")
    robust = change
    if a.has_outliers() and capped is not None and abs(capped - change) >= 0.3:
        robust = capped
        biggest = a.biggest_outlier()
        example = f" (entre ellas, el viaje de {usd(float(biggest['fare_amount']), 0)})" if biggest else ""
        if abs(capped) < STABLE_PCT:
            text += f"; sin las tarifas mayores a US$ {FARE_CAP}{example} se mantiene ({usd(cb)} → {usd(ca)})"
        else:
            text += (f"; sin las tarifas mayores a US$ {FARE_CAP}{example} la {'baja' if capped < 0 else 'suba'} es del "
                     f"{pct(abs(capped))} (de {usd(cb)} a {usd(ca)})")
    text += "."
    if median is not None and abs(median) < STABLE_PCT:
        text += f" La mediana no cambia ({usd(ma)})"
        if abs(robust) >= 1.5:
            text += f": no {'bajaron' if robust < 0 else 'subieron'} las tarifas, cambió la mezcla de viajes."
        elif abs(change) >= 1.5:
            text += ": el cambio del promedio lo explican las tarifas atípicas, no las tarifas habituales."
        else:
            text += "."
    elif median is not None:
        text += f" La mediana pasa de {usd(mb)} a {usd(ma)} ({signo(median)})"
        same_way = (median > 0) == (robust > 0)
        text += ": el cambio de tarifas es general, no solo de la mezcla." if same_way and abs(median) >= 2 else "."
    return text


def _mix_line(a: Analisis) -> str:
    parts = []
    fa, fb = a.flex_share(a.A), a.flex_share(a.B)
    if max(fa, fb) >= 0.5:
        flex_fare, rest_fare = a.fare(a.A, "avg_fare_flex"), a.fare(a.A, "avg_fare_not_flex")
        gap = variacion(flex_fare, rest_fare) or 0.0
        price = ("de tarifa parecida al resto" if abs(gap) < 2 else "más baratos" if gap < 0 else "más caros")
        parts.append(f"{'más' if fa > fb else 'menos'} viajes Flex Fare, que son {price} ({usd(flex_fare)} contra "
                     f"{usd(rest_fare)}{'' if price.startswith('de tarifa') else ' del resto'}) y pasan del {pct(fb, 0)} al {pct(fa, 0)} de los viajes"
                     if abs(fa - fb) >= 0.5 else f"una proporción estable de Flex Fare ({pct(fa, 0)})")
    aa, ab = a.airport_share(a.A), a.airport_share(a.B)
    if abs(aa - ab) >= 0.2:
        parts.append(f"{'más' if aa > ab else 'menos'} viajes a aeropuertos (del {pct(ab)} al {pct(aa)})")
    la, lb = a.p(a.A, "pct_long_trips"), a.p(a.B, "pct_long_trips")
    if abs(la - lb) >= 0.2:
        parts.append(f"{'más' if la > lb else 'menos'} viajes de más de 10 millas (del {pct(lb)} al {pct(la)})")
    if not parts:
        return ""
    text = f"En la mezcla de {a.mes_a} hay {lista(parts)}."
    if max(fa, fb) >= 0.5 and abs(fa - fb) >= 0.5:
        na, nb = a.fare(a.A, "avg_fare_not_flex"), a.fare(a.B, "avg_fare_not_flex")
        nc = variacion(na, nb)
        clean = f" y sin tarifas mayores a US$ {FARE_CAP}" if a.has_outliers() else ""
        if nc is not None:
            text += (f" Sin Flex Fare{clean}, la tarifa media casi no cambia (de {usd(nb)} a {usd(na)})." if abs(nc) < 1.5 else
                     f" Sin Flex Fare{clean}, la tarifa media {verbo(nc)} un {pct(abs(nc))} (de {usd(nb)} a {usd(na)}).")
    distance = variacion(a.p(a.A, "avg_distance"), a.p(a.B, "avg_distance"))
    if distance is not None and abs(distance) >= 2:
        text += (f" El viaje promedio es {'más largo' if distance > 0 else 'más corto'}: "
                 f"{decimal(a.p(a.A, 'avg_distance'))} contra {decimal(a.p(a.B, 'avg_distance'))} millas.")
    return text


def _quality_line(a: Analisis) -> str:
    lines = calidad_lectura(a)
    return "Calidad: " + lines[0][0].lower() + lines[0][1:] + (" " + lines[-1] if len(lines) > 1 else "")


def conclusiones(a: Analisis, command: str) -> list[str]:
    if not a.ok:
        return [f"No hay datos aceptados suficientes para comparar {a.mes_a} con {a.mes_b}; ver la sección de calidad."]
    out = []
    trips_change = variacion(a.trips(a.A), a.trips(a.B)) or 0.0
    revenue_change = variacion(a.p(a.A, "revenue"), a.p(a.B, "revenue")) or 0.0
    if abs(trips_change) < STABLE_PCT:
        demand = f"La demanda de taxis amarillos se mantiene en {a.mes_a} ({signo(trips_change)} de viajes, {signo(revenue_change)} de recaudación)."
    else:
        demand = (f"La demanda de taxis amarillos {'crece' if trips_change > 0 else 'cae'} {intensidad(trips_change)} en "
                  f"{a.mes_a} ({signo(trips_change)} de viajes, {signo(revenue_change)} de recaudación).")
    movers = sorted((z for z in a.zones.values() if z[a.B] > 0), key=lambda z: -(z[a.A] - z[a.B]) * (1 if trips_change >= 0 else -1))[:3]
    if movers:
        demand += (f" Las zonas que más {'suman' if trips_change >= 0 else 'pierden'} viajes son "
                   f"{lista([z['zone'] + ' (' + signo(variacion(z[a.A], z[a.B]) or 0) + ')' for z in movers])}")
        airport = [variacion(z[a.A], z[a.B]) for z in (a.zone_by_name(n) for n in AIRPORTS) if z and z[a.B] > 0]
        if airport and all(c is not None and c < trips_change - 3 for c in airport):
            if trips_change > 0 and all(c >= 3 for c in airport):
                demand += ", mientras los aeropuertos crecen menos que el total"
            elif trips_change > 0 and any(c >= 3 for c in airport):
                demand += ", mientras los aeropuertos quedan por debajo del total"
            else:
                demand += ", mientras los aeropuertos se quedan atrás"
        demand += "."
    out.append(demand)
    if a.p(a.A, "cbd_fee_reported") > 0:
        share_a = share(a.p(a.A, "trips_with_cbd_fee"), a.trips(a.A))
        top_cbd = [r["scope"] for r in a.q[3]["records"] if r["scope"] != "ALL ZONES"]
        growth_in_zone = sorted((z for z in a.zones.values() if z["zone"] in top_cbd and z[a.B] > 0),
                                key=lambda z: top_cbd.index(z["zone"]))
        text = f"El peaje de congestión (CBD) alcanza al {pct(share_a)} de los viajes de {a.mes_a}"
        if a.p(a.B, "cbd_fee_reported") == 0:
            changes = [variacion(z[a.A], z[a.B]) for z in growth_in_zone]
            if changes and all(c is not None and c > 0 for c in changes):
                text += (". Las zonas con mayor proporción de cobro también crecen en viajes "
                         f"({lista([z['zone'] + ' ' + signo(variacion(z[a.A], z[a.B]) or 0) for z in growth_in_zone[:3]])}): "
                         "en este mes no se observa una caída de demanda donde se cobra. Es una correlación, no una medición de causa.")
            else:
                text += f"; en {a.mes_b} todavía no existía, así que no hay comparación directa."
        else:
            share_b = share(a.p(a.B, "trips_with_cbd_fee"), a.trips(a.B))
            text += f", contra {pct(share_b)} en {a.mes_b}."
        out.append(text if text.endswith(".") else text + ".")
    distance = variacion(a.p(a.A, "avg_distance"), a.p(a.B, "avg_distance")) or 0.0
    fare = variacion(a.fare(a.A), a.fare(a.B)) or 0.0
    median = variacion(a.p(a.A, "median_fare"), a.p(a.B, "median_fare"))
    length = "más largo" if distance >= 1 else "más corto" if distance <= -1 else "igual de largo"
    price = "más caro" if fare >= 1 else "más barato" if fare <= -1 else "de tarifa parecida"
    profile = (f"El viaje promedio es {length} ({decimal(a.p(a.A, 'avg_distance'))} contra "
               f"{decimal(a.p(a.B, 'avg_distance'))} millas) y {price}"
               + (f" sin contar las tarifas mayores a US$ {FARE_CAP}" if a.has_outliers() and price != "de tarifa parecida" else ""))
    if median is not None and abs(median) < STABLE_PCT and abs(fare) >= 1.5:
        profile += f": la mediana sigue en {usd(a.p(a.A, 'median_fare'))}, así que el cambio viene de la mezcla de viajes"
        drivers = []
        if abs(a.flex_share(a.A) - a.flex_share(a.B)) >= 1:
            drivers.append(f"{'más' if a.flex_share(a.A) > a.flex_share(a.B) else 'menos'} Flex Fare")
        if abs(a.airport_share(a.A) - a.airport_share(a.B)) >= 0.3:
            drivers.append(f"{'más' if a.airport_share(a.A) > a.airport_share(a.B) else 'menos'} aeropuertos")
        if abs(a.p(a.A, "pct_long_trips") - a.p(a.B, "pct_long_trips")) >= 0.3:
            drivers.append(f"{'más' if a.p(a.A, 'pct_long_trips') > a.p(a.B, 'pct_long_trips') else 'menos'} viajes largos")
        if drivers:
            profile += f" ({lista(drivers)})"
    elif median is not None:
        profile += f" (mediana {usd(a.p(a.B, 'median_fare'))} → {usd(a.p(a.A, 'median_fare'))})"
    card_a, card_b = a.pagos[a.A].get(1), a.pagos[a.B].get(1)
    if card_a and card_b:
        tip_a, tip_b = float(card_a["avg_tip_pct"] or 0), float(card_b["avg_tip_pct"] or 0)
        profile += (f". La propina con tarjeta {'no se mueve' if abs(tip_a - tip_b) < 0.3 else 'sube' if tip_a > tip_b else 'baja'} "
                    f"({pct(tip_b, 1)} → {pct(tip_a, 1)})")
    out.append(profile + ".")
    out.append(_outliers_conclusion(a))
    out.append(_closing(a, command))
    return out


def material_outliers(a: Analisis) -> list[str]:
    """Readings that change when the fares above FARE_CAP are left out."""
    found = []
    if any(_hour_outlier(a, y) for y in (a.A, a.B)):
        found.append("el ranking de horas")
    ra, rb = a.aero.get(a.A), a.aero.get(a.B)
    if ra and rb:
        raw = variacion(float(ra["avg_fare"]), float(rb["avg_fare"]))
        capped = variacion(float(ra["avg_fare_capped"] or ra["avg_fare"]), float(rb["avg_fare_capped"] or rb["avg_fare"]))
        if raw is not None and capped is not None and abs(raw - capped) >= 1:
            found.append("la tarifa media de los aeropuertos")
    raw = variacion(a.p(a.A, "avg_fare"), a.p(a.B, "avg_fare"))
    capped = variacion(a.fare(a.A), a.fare(a.B))
    if a.has_outliers() and raw is not None and capped is not None and abs(raw - capped) >= 0.3:
        found.append("la tarifa media del mes")
    return found


def _outliers_conclusion(a: Analisis) -> str:
    over = int(a.p(a.A, "fares_over_cap") + a.p(a.B, "fares_over_cap"))
    biggest = a.biggest_outlier()
    if not over or biggest is None:
        return (f"No hay tarifas mayores a US$ {FARE_CAP} en ninguno de los dos meses, así que los promedios no están "
                "distorsionados por atípicos.")
    readings = material_outliers(a)
    who = (f"un único viaje, con una tarifa de {usd(float(biggest['fare_amount']))} ({biggest['year']}),"
           if over == 1 else f"{entero(over)} viajes con tarifas mayores a US$ {FARE_CAP} (el mayor, de "
                             f"{usd(float(biggest['fare_amount']))}, en {biggest['year']})")
    if readings:
        verb = "alcanza" if over == 1 else "alcanzan"
        return (f"Los promedios son frágiles: {who} {verb} para mover {lista(readings)}, por eso se reportan también la "
                f"mediana y el promedio sin tarifas mayores a US$ {FARE_CAP}. La siguiente regla de calidad a agregar es "
                "un tope de tarifa o de tarifa por milla.")
    return (f"Hay {who} pero no cambian ninguna lectura: los promedios con y sin ellos cuentan la misma historia. Igual "
            "conviene agregar una regla de calidad con un tope de tarifa o de tarifa por milla.")


def _closing(a: Analisis, command: str) -> str:
    qa, qb = a.quality.get(a.A), a.quality.get(a.B)
    facts = []
    for month, q in ((a.month, qa), (a.month.comparison, qb)):
        schema = (q.schema if q else {}) or {}
        found = []
        if (schema.get("derived") or {}).get("inputs"):
            found.append("formato anterior a 2011, con las zonas derivadas de las coordenadas")
        if schema.get("new_columns"):
            found.append(f"{'columna nueva ignorada' if len(schema['new_columns']) == 1 else 'columnas nuevas ignoradas'}: "
                         f"{lista(schema['new_columns'])}")
        if schema.get("missing_optional"):
            found.append(f"no trae {lista(schema['missing_optional'])}, que queda"
                         f"{'' if len(schema['missing_optional']) == 1 else 'n'} en NULL")
        if schema.get("cast_failures"):
            found.append(f"{entero(sum(schema['cast_failures'].values()))} valores no convertibles")
        if found:
            facts.append(f"{mes_es(month)}: {'; '.join(found)}")
    reported = all(q is not None and q.schema for q in (qa, qb))
    if facts:
        text = "Los archivos traen cambios de formato que el pipeline absorbe sin romperse (" + " / ".join(facts) + ")."
    elif reported:
        text = "Los dos archivos respetan el contrato de esquema."
    else:
        text = "No hay reporte de esquema de algún mes en la base de control local (las cifras de calidad salen del warehouse)."
    if qa and qb:
        text += (f" La cuarentena es del {pct(qa.pct(qa.rows_quarantined), 2)} y del {pct(qb.pct(qb.rows_quarantined), 2)} "
                 "de las filas leídas y los dos meses reconcilian.")
    engine = "Snowflake" if a.settings.warehouse == "snowflake" else "DuckDB (modo local)"
    text += f" Las cifras salen de los marts de dbt en {engine} y se reproducen con `{command}`."
    return text
