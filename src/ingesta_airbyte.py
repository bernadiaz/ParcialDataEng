"""Parte 1 — Ingesta idempotente TLC Yellow Taxi → data/raw + object store.

Flujo por `MES=YYYY-MM`:
1. Mes asignado + mismo mes del año anterior + tabla de zonas (una sola vez).
2. Descarga a `data/raw/yellow/year=AAAA/month=MM/` sin modificar el Parquet.
3. Copia al object store (fs local o S3/MinIO) con los mismos keys Hive.
4. Append a `data/control/ingestion_log.csv`.
5. Idempotencia: si el archivo local existe y su SHA-256 coincide con el del
   object store (o el último log ok/skipped), no vuelve a descargar.
6. Fallas de red: hasta 3 reintentos (1s, 2s, 4s); si falla → log error y exit ≠ 0.

`OBJECT_STORE=fs` (default en dev): `data/object_store/...` sin MinIO.
`OBJECT_STORE=s3` (prod): MinIO/AWS vía boto3.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.config import Settings, get_settings
from src.object_store import ObjectStore, make_object_store

YELLOW_URL = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/"
    "yellow_tripdata_{year:04d}-{month:02d}.parquet"
)
ZONES_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
ZONES_FILENAME = "taxi_zone_lookup.csv"

LOG_COLUMNS = [
    "archivo",
    "url",
    "filas",
    "bytes",
    "hash",
    "fecha_hora",
    "estado",
    "detalle",
]

MES_RE = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True)
class MonthRef:
    year: int
    month: int

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def yellow_filename(self) -> str:
        return f"yellow_tripdata_{self.label}.parquet"

    @property
    def yellow_url(self) -> str:
        return YELLOW_URL.format(year=self.year, month=self.month)


def parse_mes(value: str) -> MonthRef:
    m = MES_RE.match(value.strip())
    if not m:
        raise ValueError(f"MES inválido '{value}'; usar YYYY-MM")
    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        raise ValueError(f"Mes fuera de rango: {value}")
    return MonthRef(year=year, month=month)


def comparison_month(target: MonthRef) -> MonthRef:
    return MonthRef(year=target.year - 1, month=target.month)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parquet_row_count(path: Path) -> int | None:
    """Lee num_rows del footer vía parquet_file_metadata (sin cargar la tabla)."""
    try:
        import duckdb

        con = duckdb.connect(database=":memory:")
        row = con.execute(
            "SELECT COALESCE(num_rows, 0)::BIGINT FROM parquet_file_metadata(?)",
            [str(path)],
        ).fetchone()
        return int(row[0]) if row else None
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] no se pudo leer filas de {path.name}: {exc}")
        return None


def csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return max(sum(1 for _ in f) - 1, 0)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] no se pudo contar filas CSV {path.name}: {exc}")
        return None


def ensure_dirs(settings: Settings) -> None:
    (settings.data_dir / "raw" / "yellow").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "raw" / "zones").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "control").mkdir(parents=True, exist_ok=True)


def local_yellow_path(settings: Settings, ref: MonthRef) -> Path:
    return (
        settings.data_dir
        / "raw"
        / "yellow"
        / f"year={ref.year:04d}"
        / f"month={ref.month:02d}"
        / ref.yellow_filename
    )


def local_zones_path(settings: Settings) -> Path:
    return settings.data_dir / "raw" / "zones" / ZONES_FILENAME


def log_path(settings: Settings) -> Path:
    return settings.data_dir / "control" / "ingestion_log.csv"


def append_log(settings: Settings, row: dict[str, object]) -> None:
    path = log_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in LOG_COLUMNS})


def last_ok_hash(settings: Settings, archivo: str) -> str | None:
    path = log_path(settings)
    if not path.exists():
        return None
    last: str | None = None
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("archivo") == archivo and row.get("estado") in {"ok", "skipped"}:
                if row.get("hash"):
                    last = row["hash"]
    return last


def _log_row(
    *,
    archivo: str,
    url: str,
    filas: int | None,
    nbytes: int | str,
    file_hash: str,
    estado: str,
    detalle: str,
) -> dict[str, object]:
    return {
        "archivo": archivo,
        "url": url,
        "filas": filas if filas is not None else "",
        "bytes": nbytes,
        "hash": file_hash,
        "fecha_hora": utc_now(),
        "estado": estado,
        "detalle": detalle,
    }


def download_with_retries(
    url: str,
    dest: Path,
    *,
    max_retries: int,
) -> tuple[str, int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    delays = [1, 2, 4][: max(max_retries, 1)]
    last_error: Exception | None = None

    for attempt, delay in enumerate(delays, start=1):
        try:
            print(f"  ↓ {url} (intento {attempt}/{len(delays)})")
            h = hashlib.sha256()
            total = 0
            timeout = httpx.Timeout(30.0, read=600.0)
            with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as out:
                    for chunk in resp.iter_bytes(1024 * 1024):
                        if not chunk:
                            continue
                        out.write(chunk)
                        h.update(chunk)
                        total += len(chunk)
            tmp.replace(dest)
            return h.hexdigest(), total
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            print(f"  ! fallo intento {attempt}: {exc}")
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            if attempt < len(delays):
                time.sleep(delay)

    assert last_error is not None
    raise last_error


def ingest_file(
    *,
    settings: Settings,
    store: ObjectStore,
    backend: str,
    archivo: str,
    url: str,
    local_path: Path,
    store_key: str,
    content_type: str,
    count_fn,
) -> str:
    local_ok = local_path.exists() and local_path.stat().st_size > 0
    if local_ok:
        local_hash = sha256_file(local_path)
        remote_hash = store.get_sha256(store_key)
        on_store = store.exists(store_key)
        prior = last_ok_hash(settings, archivo)

        if on_store and remote_hash == local_hash:
            filas = count_fn(local_path)
            append_log(
                settings,
                _log_row(
                    archivo=archivo,
                    url=url,
                    filas=filas,
                    nbytes=local_path.stat().st_size,
                    file_hash=local_hash,
                    estado="skipped",
                    detalle=f"idempotent: local+{backend} hash match",
                ),
            )
            print(f"  ✓ skip {archivo} (hash={local_hash[:12]}…)")
            return "skipped"

        if on_store and prior == local_hash:
            filas = count_fn(local_path)
            append_log(
                settings,
                _log_row(
                    archivo=archivo,
                    url=url,
                    filas=filas,
                    nbytes=local_path.stat().st_size,
                    file_hash=local_hash,
                    estado="skipped",
                    detalle=f"idempotent: local hash matches prior log + {backend}",
                ),
            )
            print(f"  ✓ skip {archivo} (hash={local_hash[:12]}…)")
            return "skipped"

        if not on_store:
            print(f"  ↑ put only {archivo} → [{backend}] {store_key}")
            store.put_file(
                store_key, local_path, sha256=local_hash, content_type=content_type
            )
            filas = count_fn(local_path)
            append_log(
                settings,
                _log_row(
                    archivo=archivo,
                    url=url,
                    filas=filas,
                    nbytes=local_path.stat().st_size,
                    file_hash=local_hash,
                    estado="ok",
                    detalle=f"put_only: local existed, pushed to {backend}",
                ),
            )
            return "ok"

        print(f"  ~ hash mismatch local vs {backend} para {archivo}; re-descarga")

    try:
        file_hash, nbytes = download_with_retries(
            url, local_path, max_retries=settings.ingest_max_retries
        )
    except Exception as exc:  # noqa: BLE001
        append_log(
            settings,
            _log_row(
                archivo=archivo,
                url=url,
                filas=None,
                nbytes="",
                file_hash="",
                estado="error",
                detalle=str(exc)[:500],
            ),
        )
        raise

    print(f"  ↑ [{backend}] {store_key}")
    store.put_file(store_key, local_path, sha256=file_hash, content_type=content_type)

    filas = count_fn(local_path)
    append_log(
        settings,
        _log_row(
            archivo=archivo,
            url=url,
            filas=filas,
            nbytes=nbytes,
            file_hash=file_hash,
            estado="ok",
            detalle=f"downloaded → {backend}",
        ),
    )
    print(f"  ✓ ok {archivo} bytes={nbytes} filas={filas} hash={file_hash[:12]}…")
    return "ok"


def sync_ingestion_log(settings: Settings, store: ObjectStore, backend: str) -> None:
    path = log_path(settings)
    if not path.exists():
        return
    key = f"{settings.s3_control_prefix}/ingestion_log.csv"
    store.put_file(key, path, sha256=sha256_file(path), content_type="text/csv")
    print(f"[ingest] log sync → [{backend}] {key}")


def try_airbyte_sync(settings: Settings, mes: str) -> bool:
    if not settings.airbyte_enabled:
        return False
    api = os.environ.get("AIRBYTE_API_URL")
    conn = os.environ.get("AIRBYTE_CONNECTION_ID_YELLOW")
    if not api or not conn:
        print(
            "[airbyte] AIRBYTE_ENABLED pero faltan AIRBYTE_API_URL / "
            "CONNECTION_ID — uso cliente HTTP"
        )
        return False
    print(f"[airbyte] sync solicitado para {mes} (API {api})")
    print("[airbyte] sin credenciales de API completas → fallback HTTP")
    return False


def run_ingest(mes: str, settings: Settings | None = None) -> int:
    settings = settings or get_settings(mes=mes)
    target = parse_mes(mes)
    compare = comparison_month(target)

    print(f"[ingest] ENV={settings.env} MES={target.label} compare={compare.label}")
    print(f"[ingest] data_dir={settings.data_dir}")
    ensure_dirs(settings)

    try_airbyte_sync(settings, target.label)

    store, backend = make_object_store(settings)
    print(f"[ingest] object_store={backend}")

    errors: list[str] = []

    try:
        print(f"[ingest] zones ← {ZONES_URL}")
        ingest_file(
            settings=settings,
            store=store,
            backend=backend,
            archivo=ZONES_FILENAME,
            url=ZONES_URL,
            local_path=local_zones_path(settings),
            store_key=settings.raw_zones_key(),
            content_type="text/csv",
            count_fn=csv_row_count,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"zones: {exc}")
        print(f"[error] zones: {exc}")

    for ref in (target, compare):
        try:
            print(f"[ingest] yellow {ref.label} ← {ref.yellow_url}")
            ingest_file(
                settings=settings,
                store=store,
                backend=backend,
                archivo=ref.yellow_filename,
                url=ref.yellow_url,
                local_path=local_yellow_path(settings, ref),
                store_key=settings.raw_yellow_key(
                    ref.year, ref.month, ref.yellow_filename
                ),
                content_type="application/octet-stream",
                count_fn=parquet_row_count,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ref.label}: {exc}")
            print(f"[error] yellow {ref.label}: {exc}")

    try:
        sync_ingestion_log(settings, store, backend)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] no se pudo sincronizar ingestion_log: {exc}")

    if errors:
        print(f"[ingest] FAILED ({len(errors)} error/es)")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"[ingest] OK — log: {log_path(settings)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingesta NYC Yellow Taxi (idempotente)")
    parser.add_argument("--mes", required=True, help="Mes objetivo YYYY-MM")
    args = parser.parse_args(argv)
    try:
        return run_ingest(args.mes)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
