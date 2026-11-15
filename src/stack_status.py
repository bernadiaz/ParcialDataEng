"""Status of the docker compose stack (make status): is every UI reachable, and if not, why.

For each service it checks the container (created, running, healthy, restarted, killed for memory)
and its page on the published port. When something fails it says why and how to fix it, e.g.:
  - the port is taken by another program, or reserved by Windows (Hyper-V/WSL reserve port ranges:
    `netsh interface ipv4 show excludedportrange protocol=tcp`): the container is created but never
    starts, and the browser says "This site can't be reached". Set another port in .env
    (GRAFANA_PORT=3012, ...) and run `docker compose up -d` again;
  - the container stopped or keeps restarting: its last log lines are printed.

    python -m src.stack_status            # one check
    python -m src.stack_status --wait 300 # wait up to 300 s for every UI (make up)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from src.config import ROOT


@dataclass(frozen=True)
class Service:
    name: str          # docker compose service
    title: str
    port_var: str      # .env variable with the host port
    default_port: int
    path: str | None   # page that answers 200 when the service is up (None = TCP only)

    @property
    def port(self) -> int:
        value = os.environ.get(self.port_var, "").strip()
        return int(value) if value.isdigit() else self.default_port

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"


SERVICES = (
    Service("dagster", "Dagster", "DAGSTER_UI_PORT", 3003, "/server_info"),
    Service("grafana", "Grafana", "GRAFANA_PORT", 3002, "/api/health"),
    Service("superset", "Superset", "SUPERSET_PORT", 8090, "/health"),
    Service("prometheus", "Prometheus", "PROMETHEUS_PORT", 9090, "/-/healthy"),
    Service("pushgateway", "Pushgateway", "PUSHGATEWAY_PORT", 9091, "/-/healthy"),
    Service("loki", "Loki", "LOKI_PORT", 3100, "/ready"),
    Service("alloy", "Alloy", "ALLOY_PORT", 12345, "/-/ready"),
    Service("dozzle", "Dozzle", "DOZZLE_PORT", 8081, "/"),
    Service("dagster-postgres", "Dagster Postgres", "DAGSTER_PG_PORT", 5434, None),
)


@dataclass
class Status:
    service: Service
    ok: bool
    state: str
    detail: str = ""
    hint: str = ""


def _docker(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def _containers() -> dict[str, dict]:
    """compose service -> `docker inspect` of its container (empty when it was never created)."""
    listed = _docker("compose", "ps", "-a", "--format", "json")
    if listed.returncode != 0:
        raise RuntimeError(listed.stderr.strip() or "docker compose ps failed (is Docker running?)")
    text = listed.stdout.strip()
    rows = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines() if line.strip()]
    found = {}
    for row in rows:
        inspected = _docker("inspect", row["Name"])
        if inspected.returncode == 0:
            found[row["Service"]] = json.loads(inspected.stdout)[0]
    return found


def _answers(service: Service) -> bool:
    if service.path is None:
        import socket

        try:
            socket.create_connection(("127.0.0.1", service.port), timeout=3).close()
            return True
        except OSError:
            return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{service.port}{service.path}", timeout=4) as response:
            return response.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except (urllib.error.URLError, OSError):
        return False


def _windows_reserved(port: int) -> bool:
    if os.name != "nt":
        return False
    out = subprocess.run(["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
                         capture_output=True, text=True, timeout=15).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit() and int(parts[0]) <= port <= int(parts[1]):
            return True
    return False


def _logs(container: str, lines: int = 12) -> str:
    result = _docker("logs", "--tail", str(lines), container)
    return "\n".join(f"      {line[:200]}" for line in (result.stdout + result.stderr).strip().splitlines())


def check(service: Service, container: dict | None) -> Status:
    other_port = f"set another port in .env ({service.port_var}={service.port + 10}) and run `docker compose up -d`"
    if container is None:
        if _answers(service):
            return Status(service, False, "port taken", f"localhost:{service.port} answers, but not from this stack",
                          f"another program uses port {service.port}: stop it, or {other_port}")
        return Status(service, False, "not created", "", "run `docker compose up -d` in the repository folder")
    state = container["State"]
    health = (state.get("Health") or {}).get("Status", "")
    restarts = container.get("RestartCount", 0)
    if not state.get("Running"):
        error = state.get("Error", "")
        if "port" in error.lower() or "bind" in error.lower() or "socket" in error.lower():
            reserved = _windows_reserved(service.port)
            reason = (f"Windows reserves port {service.port} (Hyper-V/WSL excluded port range)" if reserved
                      else f"port {service.port} is taken by another program")
            return Status(service, False, "port not available", error, f"{reason}: {other_port}")
        if state.get("OOMKilled"):
            return Status(service, False, "killed: out of memory", _logs(container["Name"].lstrip("/")),
                          "give Docker more memory (Docker Desktop > Settings > Resources) or raise its mem_limit")
        status = state.get("Status", "")
        return Status(service, False, status or "stopped", error or _logs(container["Name"].lstrip("/")),
                      "`docker compose up -d` starts it again; its last log lines are above")
    if _answers(service):
        note = f" (restarted {restarts} times)" if restarts else ""
        return Status(service, True, (health or "running") + note)
    if health == "starting" or (time.time() - _started_epoch(state) < 120):
        return Status(service, False, "starting", "", "it is still starting (Superset needs 1-2 minutes the first time)")
    return Status(service, False, f"running, page not answering{f', {health}' if health else ''}",
                  _logs(container["Name"].lstrip("/")),
                  f"check that nothing else answers on localhost:{service.port}, then `docker compose restart {service.name}`")


def _started_epoch(state: dict) -> float:
    from datetime import datetime

    try:
        return datetime.fromisoformat(state.get("StartedAt", "")[:26].replace("Z", "") + "+00:00").timestamp()
    except ValueError:
        return 0.0


def check_all() -> list[Status]:
    containers = _containers()
    return [check(service, containers.get(service.name)) for service in SERVICES]


def report(statuses: list[Status]) -> str:
    lines = []
    for s in statuses:
        mark = "OK  " if s.ok else "FAIL"
        lines.append(f"{mark} {s.service.title:17s} {s.service.url:24s} {s.state}")
        if not s.ok:
            if s.detail:
                lines.append(s.detail if s.detail.startswith("      ") else f"      {s.detail}")
            if s.hint:
                lines.append(f"      -> {s.hint}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS", help="wait until every UI answers")
    args = parser.parse_args(argv)
    if not shutil.which("docker"):
        print("Docker is not installed or not in PATH.", file=sys.stderr)
        return 1
    deadline = time.monotonic() + args.wait
    while True:
        try:
            statuses = check_all()
        except RuntimeError as exc:
            print(f"Docker is not answering: {exc}", file=sys.stderr)
            return 1
        waiting = [s for s in statuses if not s.ok and s.state in {"starting", "not created"}]
        if all(s.ok for s in statuses) or not waiting or time.monotonic() >= deadline:
            break
        time.sleep(5)
    print(report(statuses))
    return 0 if all(s.ok for s in statuses) else 1


if __name__ == "__main__":
    sys.exit(main())
