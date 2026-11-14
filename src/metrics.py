"""Métricas del pipeline → Prometheus Pushgateway.

Uso:
  python -m src.metrics --mes 2025-03 --stage quality --success 1 --duration 45.2
  python -m src.metrics --mes 2025-03 --push-reports

No falla el pipeline si Pushgateway está caído (solo warning).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict

import httpx

from src.config import Settings, get_settings
from src.modelo import warehouse_path


def _escape_label(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def _sample(name: str, value: float, labels: dict[str, str]) -> str:
    parts = ",".join(
        f'{k}="{_escape_label(v)}"' for k, v in sorted(labels.items())
    )
    return f"{name}{{{parts}}} {float(value)}"


def render_exposition(series: dict[str, list[str]]) -> str:
    """series: metric_name -> list of sample lines (sin TYPE)."""
    out: list[str] = []
    for name in sorted(series):
        out.append(f"# TYPE {name} gauge")
        out.extend(series[name])
    return "\n".join(out) + "\n"


def push_metrics(
    *,
    settings: Settings,
    job: str,
    grouping: dict[str, str],
    series: dict[str, list[str]],
) -> bool:
    base = (settings.pushgateway_url or "").rstrip("/")
    if not base or not settings.metrics_enabled:
        print("[metrics] skip (METRICS_ENABLED=0 o sin PUSHGATEWAY_URL)")
        return False

    path = "/".join(
        [f"job/{job}"]
        + [f"{k}/{v}" for k, v in grouping.items()]
    )
    url = f"{base}/metrics/{path}"
    body = render_exposition(series)
    try:
        # PUT reemplaza el grupo; DELETE previo evita inconsistencias de pushes rotos.
        httpx.delete(url, timeout=5.0)
        resp = httpx.put(
            url,
            content=body.encode("utf-8"),
            headers={"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
            timeout=10.0,
        )
        if resp.status_code >= 400:
            print(f"[metrics] WARN HTTP {resp.status_code}: {resp.text[:500]}")
            return False
        n = sum(len(v) for v in series.values())
        print(f"[metrics] pushed → {url} ({n} series)")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[metrics] WARN no se pudo pushear: {exc}")
        return False


def push_stage(
    *,
    settings: Settings,
    mes: str,
    stage: str,
    success: bool,
    duration_s: float | None = None,
) -> None:
    labels = {"mes": mes, "env": settings.env, "stage": stage}
    series: dict[str, list[str]] = defaultdict(list)
    series["nyc_taxi_stage_success"].append(
        _sample("nyc_taxi_stage_success", 1.0 if success else 0.0, labels)
    )
    if duration_s is not None:
        series["nyc_taxi_stage_duration_seconds"].append(
            _sample("nyc_taxi_stage_duration_seconds", float(duration_s), labels)
        )
    series["nyc_taxi_stage_last_unixtime"].append(
        _sample("nyc_taxi_stage_last_unixtime", float(time.time()), labels)
    )
    push_metrics(
        settings=settings,
        job="nyc_taxi_pipeline",
        grouping={"mes": mes, "stage": stage},
        series=series,
    )


def collect_from_reports(
    settings: Settings, mes: str
) -> dict[str, list[str]]:
    series: dict[str, list[str]] = defaultdict(list)
    labels_base = {"mes": mes, "env": settings.env}

    qpath = settings.data_dir / "reports" / f"quality_report_{mes}.json"
    if qpath.exists():
        data = json.loads(qpath.read_text(encoding="utf-8"))
        for month in data.get("months", []):
            m = str(month.get("mes", mes))
            lb = {"mes": m, "env": settings.env}
            series["nyc_taxi_quality_rows_read"].append(
                _sample("nyc_taxi_quality_rows_read", month["rows_read"], lb)
            )
            series["nyc_taxi_quality_rows_accepted"].append(
                _sample(
                    "nyc_taxi_quality_rows_accepted", month["rows_accepted"], lb
                )
            )
            series["nyc_taxi_quality_rows_quarantine"].append(
                _sample(
                    "nyc_taxi_quality_rows_quarantine",
                    month["rows_quarantine"],
                    lb,
                )
            )
            series["nyc_taxi_quality_reconciled"].append(
                _sample(
                    "nyc_taxi_quality_reconciled",
                    1.0 if month.get("reconciled") else 0.0,
                    lb,
                )
            )
            for rule_id, cnt in (month.get("per_rule") or {}).items():
                series["nyc_taxi_quality_rule_violations"].append(
                    _sample(
                        "nyc_taxi_quality_rule_violations",
                        float(cnt),
                        {**lb, "rule_id": str(rule_id)},
                    )
                )

    log = settings.data_dir / "control" / "ingestion_log.csv"
    if log.exists():
        last: dict[str, str] = {}
        with log.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                archivo = (row.get("archivo") or "").strip()
                if archivo:
                    last[archivo] = (row.get("estado") or "").strip()
        status_map = {"error": 0.0, "ok": 1.0, "skipped": 2.0}
        for archivo, estado in last.items():
            # sanitizar label: Pushgateway no ama paths raros
            safe = archivo.replace("/", "_")
            series["nyc_taxi_ingest_last_status"].append(
                _sample(
                    "nyc_taxi_ingest_last_status",
                    status_map.get(estado, -1.0),
                    {**labels_base, "archivo": safe, "estado": estado or "unknown"},
                )
            )

    wh = warehouse_path(settings)
    if wh.exists():
        try:
            import duckdb

            con = duckdb.connect(str(wh), read_only=True)
            tables = {
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'marts'"
                ).fetchall()
            }
            if "fact_trips" in tables:
                n = con.execute(
                    "SELECT count(*) FROM marts.fact_trips"
                ).fetchone()[0]
                series["nyc_taxi_fact_trips"].append(
                    _sample("nyc_taxi_fact_trips", float(n), labels_base)
                )
            for table in ("dim_zone", "dim_date", "agg_zone_hour"):
                if table not in tables:
                    continue
                c = con.execute(
                    f"SELECT count(*) FROM marts.{table}"
                ).fetchone()[0]
                series["nyc_taxi_mart_rows"].append(
                    _sample(
                        "nyc_taxi_mart_rows",
                        float(c),
                        {**labels_base, "table": table},
                    )
                )
            con.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[metrics] WARN warehouse: {exc}")

    return series


def run_push_reports(mes: str, settings: Settings) -> int:
    series = collect_from_reports(settings, mes)
    if not series:
        print("[metrics] no hay reportes/warehouse para pushear")
        return 0
    # No poner `mes` en el grouping: el reporte incluye varios meses y
    # Pushgateway inyectaría el mismo mes en todas las series → duplicados.
    ok = push_metrics(
        settings=settings,
        job="nyc_taxi_pipeline",
        grouping={"stage": "reports"},
        series=series,
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Push métricas a Pushgateway")
    parser.add_argument("--mes", required=True)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--success", type=int, default=1)
    parser.add_argument("--duration", type=float, default=None)
    parser.add_argument(
        "--push-reports",
        action="store_true",
        help="Lee reports/warehouse y pushea gauges de negocio",
    )
    args = parser.parse_args(argv)
    settings = get_settings(mes=args.mes)

    if args.push_reports:
        return run_push_reports(args.mes, settings)

    if not args.stage:
        print("[error] indicá --stage o --push-reports", file=sys.stderr)
        return 2

    push_stage(
        settings=settings,
        mes=args.mes,
        stage=args.stage,
        success=bool(args.success),
        duration_s=args.duration,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
