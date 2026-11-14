"""Object store abstracto: S3/MinIO o filesystem local (mismos keys Hive).

En notebooks de 8 GB, `OBJECT_STORE=fs` evita depender de MinIO/Docker Hub.
Los keys son idénticos a S3 (`raw/yellow/year=...`), así DuckDB puede leer
desde `data/object_store/` o desde S3 sin cambiar el contrato de paths.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.config import Settings
from src.s3util import (
    ensure_bucket,
    head_object,
    make_s3_client,
    object_exists,
    upload_file,
)


class ObjectStore(Protocol):
    def exists(self, key: str) -> bool: ...

    def get_sha256(self, key: str) -> str | None: ...

    def put_file(self, key: str, path: Path, *, sha256: str, content_type: str | None = None) -> None: ...


@dataclass
class FsObjectStore:
    """Copia archivos bajo `{data_dir}/object_store/{key}` + sidecar `.sha256`."""

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def _meta_path(self, key: str) -> Path:
        return self.root / f"{key}.meta.json"

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def get_sha256(self, key: str) -> str | None:
        meta = self._meta_path(key)
        if meta.is_file():
            try:
                return json.loads(meta.read_text(encoding="utf-8")).get("sha256")
            except json.JSONDecodeError:
                return None
        return None

    def put_file(self, key: str, path: Path, *, sha256: str, content_type: str | None = None) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)
        self._meta_path(key).write_text(
            json.dumps({"sha256": sha256, "content_type": content_type}, indent=None),
            encoding="utf-8",
        )


@dataclass
class S3ObjectStore:
    settings: Settings
    client: object

    def exists(self, key: str) -> bool:
        return object_exists(self.client, self.settings.s3_bucket, key)

    def get_sha256(self, key: str) -> str | None:
        meta = head_object(self.client, self.settings.s3_bucket, key)
        if not meta:
            return None
        md = meta.get("Metadata") or {}
        return md.get("sha256") or md.get("Sha256")

    def put_file(self, key: str, path: Path, *, sha256: str, content_type: str | None = None) -> None:
        upload_file(
            self.client,
            bucket=self.settings.s3_bucket,
            key=key,
            path=str(path),
            sha256=sha256,
            content_type=content_type,
        )


def make_object_store(settings: Settings) -> tuple[ObjectStore, str]:
    """Retorna (store, backend_name). backend: fs | s3."""
    backend = (settings.object_store or "fs").strip().lower()
    if backend == "s3":
        client = make_s3_client(settings)
        ensure_bucket(client, settings.s3_bucket)
        return S3ObjectStore(settings=settings, client=client), "s3"
    # default / fs
    root = settings.data_dir / "object_store"
    return FsObjectStore(root=root), "fs"
