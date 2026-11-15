"""make status: a UI that does not answer is explained (port taken or reserved, stopped, out of memory)."""
from __future__ import annotations

from src import stack_status
from src.dashboards import superset_url

GRAFANA = next(s for s in stack_status.SERVICES if s.name == "grafana")


def _container(running: bool, error: str = "", oom: bool = False, health: str = "") -> dict:
    state = {"Running": running, "Status": "running" if running else "created", "Error": error, "OOMKilled": oom,
             "StartedAt": "2026-01-01T00:00:00Z"}
    if health:
        state["Health"] = {"Status": health}
    return {"Name": "/nyc-taxi-grafana-1", "State": state, "RestartCount": 0}


def test_port_taken_by_another_program_is_explained(monkeypatch):
    monkeypatch.setattr(stack_status, "_windows_reserved", lambda port: False)
    error = "Bind for 127.0.0.1:3002 failed: port is already allocated"
    status = stack_status.check(GRAFANA, _container(False, error))
    assert not status.ok and status.state == "port not available"
    assert "GRAFANA_PORT=3012" in status.hint and "taken by another program" in status.hint


def test_port_reserved_by_windows_is_explained(monkeypatch):
    monkeypatch.setattr(stack_status, "_windows_reserved", lambda port: True)
    error = "listen tcp 127.0.0.1:3002: bind: An attempt was made to access a socket in a way forbidden by its access permissions."
    status = stack_status.check(GRAFANA, _container(False, error))
    assert "Windows reserves port 3002" in status.hint and "GRAFANA_PORT" in status.hint


def test_out_of_memory_and_healthy_containers(monkeypatch):
    monkeypatch.setattr(stack_status, "_logs", lambda name, lines=12: "")
    assert "memory" in stack_status.check(GRAFANA, _container(False, oom=True)).state
    monkeypatch.setattr(stack_status, "_answers", lambda service: True)
    assert stack_status.check(GRAFANA, _container(True, health="healthy")).ok


def test_ports_come_from_env(monkeypatch):
    monkeypatch.setenv("GRAFANA_PORT", "3012")
    assert GRAFANA.url == "http://localhost:3012"
    monkeypatch.delenv("SUPERSET_URL", raising=False)
    monkeypatch.setenv("SUPERSET_PORT", "8095")
    assert superset_url() == "http://localhost:8095"
