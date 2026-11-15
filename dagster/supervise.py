"""Entry point of the Dagster UI container.

1. Points the instance at the Postgres of docker compose and registers MES and its comparison month
   (src/dagster_instance.py), so a new UI shows every asset grey until `make all` runs.
2. Serves the UI read only on port 3003.
3. Watches the mounted repository (Python, dbt, contracts). The UI loads the code once, at start, so
   after a `git pull` or an edit it would keep showing the old lineage: when a file changes, the
   webserver restarts (about 15 s) and shows the new definitions.
"""
import hashlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/opt/nyc_taxi")
WATCHED = ("src", "dbt_taxi/models", "dbt_taxi/macros", "dbt_taxi/tests", "dbt_taxi/dbt_project.yml",
           "dbt_taxi/profiles.yml", "contracts")
SUFFIXES = {".py", ".sql", ".yml", ".yaml"}
POLL_SECONDS = 10
WEBSERVER = ["dagster-webserver", "-h", "0.0.0.0", "-p", "3003", "-m", "src.orchestration", "-d", str(ROOT), "--read-only"]


def fingerprint() -> str:
    digest = hashlib.sha1()
    for entry in WATCHED:
        path = ROOT / entry
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.suffix in SUFFIXES and p.is_file())
        for file in files:
            try:
                stat = file.stat()
            except OSError:
                continue
            digest.update(f"{file.relative_to(ROOT)}:{stat.st_mtime_ns}:{stat.st_size}\n".encode())
    return digest.hexdigest()


def main() -> int:
    os.chdir(ROOT)
    subprocess.run([sys.executable, "-m", "src.dagster_instance", "--months", os.environ.get("MES", "2025-01")], check=True)
    current: dict[str, subprocess.Popen] = {}

    def stop(signum, frame):  # docker stop: end the webserver cleanly, then exit
        proc = current.get("webserver")
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(20)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while True:
        seen = fingerprint()
        proc = current["webserver"] = subprocess.Popen(WEBSERVER)
        while proc.poll() is None:
            time.sleep(POLL_SECONDS)
            if fingerprint() != seen:
                print("Code changed in the repository: restarting the Dagster UI to load it", flush=True)
                proc.terminate()
                try:
                    proc.wait(30)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
        else:
            return proc.returncode or 1  # the webserver died on its own: let Docker restart the container


if __name__ == "__main__":
    sys.exit(main())
