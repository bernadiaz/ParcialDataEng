"""Observability: metrics for Prometheus (via Pushgateway) and JSON log lines for Loki.

- Metrics: every step pushes its numbers to the Pushgateway (PUSHGATEWAY_URL, default
  http://localhost:9091), and Prometheus scrapes them. A batch job ends before Prometheus could
  scrape it, so the Pushgateway is the standard pattern. Metrics are grouped by {job, step, mes}.
  A data push (rows, violations, loads) replaces its group (PUT), so reruns overwrite instead of
  piling up. The step's run metrics (duration, RAM, success) are pushed with POST at the end of the
  step: POST replaces only the metrics with the same name, so they never wipe the data metrics the
  step pushed into the same group. If the gateway is down, the pipeline logs one warning and
  continues: observability must never break a run.
- Logs: besides stdout (Dozzle shows it when the pipeline runs in Docker), every log line is
  written as JSON to data/logs/pipeline.jsonl. Grafana Alloy tails that file and ships it to Loki.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

JOB = "nyc_taxi_pipeline"
_warned = False


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "run_id": self.run_id,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def json_file_handler(data_dir: Path, run_id: str) -> logging.Handler | None:
    """File handler for Loki, unless LOG_TO_FILE=0 (tests)."""
    if os.environ.get("LOG_TO_FILE", "1") == "0":
        return None
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "pipeline.jsonl", encoding="utf-8")
    handler.setFormatter(JsonFormatter(run_id))
    return handler


def _gateway() -> str:
    from src.config import loopback

    url = os.environ.get("PUSHGATEWAY_URL", "http://localhost:9091").strip()
    return loopback(url) if url else ""


def push(step: str, mes: str, samples: Iterable[tuple[str, str, dict[str, str], float]], *, replace: bool = True) -> None:
    """Pushes (metric, help, labels, value) samples to the Pushgateway group {job, step, mes}.

    replace=True (PUT) swaps the whole group. replace=False (POST) only swaps the metrics with the
    same name and keeps the rest of the group.
    """
    global _warned
    gateway = _gateway()
    if not gateway:
        return
    try:
        import prometheus_client
        from prometheus_client import CollectorRegistry, Gauge

        registry = CollectorRegistry()
        gauges: dict[str, Gauge] = {}
        for name, help_text, labels, value in samples:
            if name not in gauges:
                gauges[name] = Gauge(name, help_text, sorted(labels), registry=registry)
            gauge = gauges[name]
            (gauge.labels(**labels) if labels else gauge).set(value)
        send = prometheus_client.push_to_gateway if replace else prometheus_client.pushadd_to_gateway
        send(gateway, job=JOB, registry=registry, grouping_key={"step": step, "mes": mes}, timeout=3)
    except Exception as exc:  # gateway down or not installed: never fail the pipeline
        if not _warned:
            logging.getLogger("observability").warning("Pushgateway %s not reachable (%s): metrics skipped", gateway, exc)
            _warned = True


def push_step(step: str, mes: str, seconds: float, peak_rss_mb: float | None, ok: bool) -> None:
    now = datetime.now(timezone.utc).timestamp()
    push(step, mes, [
        ("nyc_taxi_step_duration_seconds", "Duration of the last run of a pipeline step", {}, seconds),
        ("nyc_taxi_step_peak_rss_megabytes", "Peak resident memory of the step process", {}, peak_rss_mb or 0.0),
        ("nyc_taxi_step_success", "1 if the last run of the step succeeded", {}, 1.0 if ok else 0.0),
        ("nyc_taxi_step_last_run_timestamp_seconds", "End time of the last run of the step", {}, now),
    ], replace=False)  # keep the data metrics the step pushed into the same group (e.g. quality)
