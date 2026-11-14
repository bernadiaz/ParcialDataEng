"""Cliente S3 / MinIO compartido por el pipeline."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from src.config import Settings


def resolve_endpoint(settings: Settings) -> str | None:
    """En el host, reescribe http://minio:9000 → localhost (Compose usa el hostname minio)."""
    endpoint = settings.s3_endpoint_url
    if not endpoint:
        return None
    in_docker = _running_in_docker()
    if not in_docker and "://" in endpoint:
        # http://minio:9000 → http://localhost:9000
        scheme, rest = endpoint.split("://", 1)
        hostport = rest.split("/", 1)[0]
        host, _, port = hostport.partition(":")
        if host == "minio":
            host = "localhost"
            endpoint = f"{scheme}://{host}{':' + port if port else ''}"
    return endpoint


def _running_in_docker() -> bool:
    from pathlib import Path

    return Path("/.dockerenv").exists()


def make_s3_client(settings: Settings) -> BaseClient:
    endpoint = resolve_endpoint(settings)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        region_name=settings.s3_region,
        config=Config(
            s3={"addressing_style": "path" if settings.s3_path_style else "virtual"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def ensure_bucket(client: BaseClient, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        client.create_bucket(Bucket=bucket)


def object_exists(client: BaseClient, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def head_object(client: BaseClient, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except Exception:
        return None


def upload_file(
    client: BaseClient,
    *,
    bucket: str,
    key: str,
    path: str,
    sha256: str,
    content_type: str | None = None,
) -> None:
    extra: dict[str, Any] = {"Metadata": {"sha256": sha256}}
    if content_type:
        extra["ContentType"] = content_type
    client.upload_file(path, bucket, key, ExtraArgs=extra)
