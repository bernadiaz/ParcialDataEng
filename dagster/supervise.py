"""Entry point of the Dagster UI container.

1. Points the instance at the Postgres of docker compose and registers MES and its comparison month
   (src/dagster_instance.py), so a new UI shows every asset grey until `make all` runs.
2. Serves the UI read only on port 3003.
3. Watches the mounted repository (Python, dbt, contracts). The UI loads the code once, at start, so
   after a `git pull` or an edit it would keep showing the old lineage: when a file changes, the
   webserver restarts (about 15 s) and shows the new definitions.

The webserver runs from DAGSTER_HOME, not from the repository. dagster-webserver (and the code server
it starts) loads the .env of its working directory and lets it override the environment. The .env of
the repository holds the values of the host (DAGSTER_PG_PORT=5434 or 5436, DATA_DIR=~/...), so the UI
looked for its Postgres at dagster-postgres:5434, gave up after about 30 s and the container restarted
forever ("starting" in make status). From DAGSTER_HOME, which has no .env, the settings of
docker-compose.yml always win. src/config.py still reads the rest of the .env without overriding them.
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
    # A folder without .env (see the docstring): the code is still loaded from ROOT through -d.
    workdir = Path(os.environ.get("DAGSTER_HOME") or "/opt/dagster/home")
    workdir.mkdir(parents=True, exist_ok=True)
    while True:
        seen = fingerprint()
        proc = current["webserver"] = subprocess.Popen(WEBSERVER, cwd=workdir)
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
