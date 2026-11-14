"""Ejecuta sql/q1–q6 contra el warehouse DuckDB y escribe RESULTADOS.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb

from src.config import ROOT, Settings, get_settings
from src.ingesta_airbyte import comparison_month, parse_mes
from src.modelo import warehouse_path

SQL_DIR = ROOT / "sql"

QUERIES = [
    ("q1", "q1_top_zones_variation.sql", "Top 10 zonas de origen y variación vs mes comparación"),
    ("q2", "q2_peak_hour_avg_revenue.sql", "Hora con mayor ingreso promedio por viaje"),
    ("q3a", "q3_cbd_fee_share.sql", "% viajes con cbd_congestion_fee > 0 (mes asignado)"),
    ("q3b", "q3b_cbd_top_zones.sql", "Top 5 zonas origen por proporción CBD fee > 0"),
    ("q4", "q4_tip_pct_by_payment.sql", "Propina promedio (% tarifa) por tipo de pago"),
    ("q5", "q5_airport_trips.sql", "Viajes y tarifa media JFK / LaGuardia"),
    ("q6", "q6_month_variation.sql", "Variación viajes y tarifa media entre meses"),
]


def _strip_comments(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def render_sql(path: Path, params: dict[str, int | str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in params.items():
        text = text.replace("{{" + key + "}}", str(value))
    if "{{" in text:
        missing = re.findall(r"\{\{(\w+)\}\}", text)
        raise ValueError(f"Placeholders sin resolver en {path.name}: {missing}")
    return _strip_comments(text)


def _fmt_table(columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return "_Sin filas._\n"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        cells = []
        for v in row:
            if v is None:
                cells.append("NULL")
            elif isinstance(v, float):
                cells.append(f"{v:.6g}")
            else:
                cells.append(str(v))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *body]) + "\n"


def _interpretations(mes: str, compare: str, results: dict[str, object]) -> dict[str, str]:
    """Borradores de interpretación (revisar/ajustar en la defensa oral)."""
    return {
        "q1": (
            f"Las zonas con más orígenes en {mes} concentran la demanda Manhattan/aeropuertos; "
            f"la variación vs {compare} muestra dónde creció o cayó el tráfico yellow."
        ),
        "q2": (
            "La hora pico de ingreso promedio suele alinearse con traslados largos "
            "(aeropuerto/madrugada) más que con el horario de máximo volumen."
        ),
        "q3": (
            f"El CBD congestion fee aplica en {mes} (archivo 2025+). Las zonas con mayor "
            "proporción concentran pickups dentro/hacia el distrito de congestion pricing."
        ),
        "q4": (
            "Credit card (1) registra propina en el datáfono; **Cash (2) no es interpretable**: "
            "la propina en efectivo casi nunca entra en `tip_amount`, por eso el % queda sesgado "
            "hacia 0. No charge/Dispute tampoco reflejan propina real."
        ),
        "q5": (
            "JFK y LaGuardia concentran viajes de mayor tarifa media que el promedio urbano "
            "por distancia y airport fee."
        ),
        "q6": (
            f"Entre {compare} y {mes} cambia el volumen y/o la tarifa media. "
            "Hipótesis: (1) recuperación/estacionalidad de demanda yellow; "
            "(2) efecto del CBD congestion fee y surcharges en 2025; "
            "(3) cambios de oferta (Uber/Lyft) que desplazan viajes cortos; "
            "(4) inflación de tarifas TLC; "
            "(5) calidad de datos/filtrado de cuarentena distinto entre años."
        ),
    }


def run_questions(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)
    wh = warehouse_path(settings)
    if not wh.exists():
        print(f"[error] No existe warehouse {wh}. Corré `make model-host` antes.")
        return 1

    params = {
        "target_year": target.year,
        "target_month": target.month,
        "compare_year": compare.year,
        "compare_month": compare.month,
    }

    print(f"[questions] ENV={settings.env} MES={target.label} compare={compare.label}")
    print(f"[questions] warehouse={wh}")

    con = duckdb.connect(str(wh), read_only=True)
    blocks: list[tuple[str, str, str, str]] = []
    # id -> (title, sql_path, table_md)
    stored: dict[str, tuple[str, str, str]] = {}

    for qid, filename, title in QUERIES:
        path = SQL_DIR / filename
        sql = render_sql(path, params)
        print(f"  → {qid}: {filename}")
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        table = _fmt_table(cols, rows)
        stored[qid] = (title, str(path.relative_to(ROOT)), table)

    inter = _interpretations(target.label, compare.label, stored)

    # Ensamblar RESULTADOS.md al estilo consigna
    out = ROOT / "RESULTADOS.md"
    md = [
        "# RESULTADOS — preguntas de negocio",
        "",
        f"Mes asignado: **{target.label}**. Comparación: **{compare.label}**.",
        "",
        f"> Generado con `make questions-host MES={target.label}` sobre `marts.*` "
        f"en `{wh.relative_to(ROOT)}`.",
        "",
        "## 1. Top 10 zonas de origen y variación vs 2024",
        "",
        f"Consulta: `{stored['q1'][1]}`",
        "",
        stored["q1"][2],
        f"Interpretación: {inter['q1']}",
        "",
        "## 2. Hora con mayor ingreso promedio por viaje",
        "",
        f"Consulta: `{stored['q2'][1]}`",
        "",
        stored["q2"][2],
        f"Interpretación: {inter['q2']}",
        "",
        "## 3. CBD congestion fee (> 0) y top 5 zonas",
        "",
        f"Consulta: `{stored['q3a'][1]}` + `{stored['q3b'][1]}`",
        "",
        "### Global (mes asignado)",
        "",
        stored["q3a"][2],
        "### Top 5 zonas de origen (mín. 1000 viajes)",
        "",
        stored["q3b"][2],
        f"Interpretación: {inter['q3']}",
        "",
        "## 4. Propina promedio (% tarifa) por tipo de pago",
        "",
        f"Consulta: `{stored['q4'][1]}`",
        "",
        stored["q4"][2],
        f"Interpretación: {inter['q4']}",
        "",
        "## 5. Viajes y tarifa media JFK / LaGuardia",
        "",
        f"Consulta: `{stored['q5'][1]}`",
        "",
        stored["q5"][2],
        f"Interpretación: {inter['q5']}",
        "",
        "## 6. Variación entre los dos meses",
        "",
        f"Consulta: `{stored['q6'][1]}`",
        "",
        stored["q6"][2],
        "Hipótesis de causa (≤ 5 líneas):",
        "",
        inter["q6"],
        "",
    ]
    out.write_text("\n".join(md), encoding="utf-8")
    con.close()
    print(f"[questions] OK → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preguntas de negocio → RESULTADOS.md")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_questions(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
