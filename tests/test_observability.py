"""Pushgateway grouping: a step's run metrics must not wipe the data metrics of the same group.

Regression test: the quality step pushes nyc_taxi_rows / nyc_taxi_rule_violations / nyc_taxi_reconciled
to the group {step="quality", mes}. track_step then pushed the step's run metrics to the same group
with PUT, which replaced the whole group, so Grafana's Data Quality dashboard showed "No data".
"""
from __future__ import annotations

import prometheus_client
import pytest

from src import observability


class FakeGateway:
    """Pushgateway semantics: PUT replaces the group, POST replaces only the metrics with the same name."""

    def __init__(self) -> None:
        self.groups: dict[tuple, dict[str, list]] = {}

    @staticmethod
    def _families(registry) -> dict[str, list]:
        return {f.name: [(s.labels, s.value) for s in f.samples] for f in registry.collect()}

    def put(self, gateway, job, registry, grouping_key, timeout):  # noqa: ARG002
        self.groups[(job, tuple(sorted(grouping_key.items())))] = self._families(registry)

    def post(self, gateway, job, registry, grouping_key, timeout):  # noqa: ARG002
        group = self.groups.setdefault((job, tuple(sorted(grouping_key.items()))), {})
        group.update(self._families(registry))

    def metrics(self, step: str, mes: str) -> set[str]:
        return set(self.groups.get((observability.JOB, (("mes", mes), ("step", step))), {}))


@pytest.fixture
def gateway(monkeypatch) -> FakeGateway:
    fake = FakeGateway()
    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway.test:9091")
    monkeypatch.setattr(prometheus_client, "push_to_gateway", fake.put)
    monkeypatch.setattr(prometheus_client, "pushadd_to_gateway", fake.post)
    return fake


def quality_samples(read: float) -> list:
    return [
        ("nyc_taxi_rows", "Rows per quality outcome", {"outcome": "read"}, read),
        ("nyc_taxi_reconciled", "1 if rows read = accepted + quarantined", {}, 1.0),
    ]


def test_step_metrics_keep_the_quality_metrics_of_the_same_group(gateway):
    observability.push("quality", "2025-01", quality_samples(3_475_226))
    observability.push_step("quality", "2025-01", seconds=9.4, peak_rss_mb=512, ok=True)

    assert gateway.metrics("quality", "2025-01") >= {
        "nyc_taxi_rows", "nyc_taxi_reconciled", "nyc_taxi_step_duration_seconds", "nyc_taxi_step_success",
    }


def test_rerun_replaces_the_data_metrics_of_the_group(gateway):
    observability.push("quality", "2025-01", quality_samples(1.0))
    observability.push("quality", "2025-01", [("nyc_taxi_rows", "Rows per quality outcome", {"outcome": "read"}, 2.0)])

    group = gateway.groups[(observability.JOB, (("mes", "2025-01"), ("step", "quality")))]
    assert set(group) == {"nyc_taxi_rows"}  # the stale nyc_taxi_reconciled of the first run is gone
    assert group["nyc_taxi_rows"][0][1] == 2.0


def test_a_run_keeps_only_the_groups_of_its_two_months(monkeypatch):
    """make all MES=2025-02 removes the groups of other months, so Grafana shows its comparison only."""
    import io
    import json
    import urllib.request

    groups = [{"labels": {"job": observability.JOB, "step": step, "mes": mes}}
              for step, mes in (("quality", "2025-01"), ("quality", "2024-01"), ("quality", "2025-02"),
                                ("quality", "2024-02"), ("ingest-zones", "static"), ("dbt", "2025-02,2024-02"),
                                ("dbt", "2025-01,2024-01"))]
    groups.append({"labels": {"job": "another_job", "step": "x", "mes": "2020-01"}})
    deleted: list[str] = []

    def fake_urlopen(request, timeout=None):  # noqa: ARG001
        if isinstance(request, urllib.request.Request) and request.get_method() == "DELETE":
            deleted.append(request.full_url.split("/metrics/job/", 1)[1])
            return io.BytesIO(b"")
        return io.BytesIO(json.dumps({"status": "success", "data": groups}).encode())

    monkeypatch.setenv("PUSHGATEWAY_URL", "http://pushgateway.test:9091")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    removed = observability.keep_only_months(["2025-02", "2024-02"])

    assert sorted(removed) == ["dbt/2025-01,2024-01", "quality/2024-01", "quality/2025-01"]
    assert all(d.startswith(f"{observability.JOB}/step/") for d in deleted) and len(deleted) == 3
