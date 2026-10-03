"""MinIO / local filesystem S3-compatible object store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import Settings


class ObjectStore:
    """Stores raw + recognized artifacts. Uses local FS when MinIO unavailable."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket = settings.minio_bucket
        self._local_root = Path(__file__).resolve().parents[3] / "data" / "object-store" / self.bucket
        self._local_root.mkdir(parents=True, exist_ok=True)
        self._client = None
        if settings.store_backend == "live":
            try:
                from minio import Minio

                self._client = Minio(
                    settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure,
                )
                if not self._client.bucket_exists(self.bucket):
                    self._client.make_bucket(self.bucket)
            except Exception:
                self._client = None

    def _key(self, prefix: str, asset_id: str, filename: str) -> str:
        return f"{prefix}/{asset_id}/{filename}"

    def put_bytes(self, prefix: str, asset_id: str, filename: str, data: bytes, content_type: str) -> str:
        key = self._key(prefix, asset_id, filename)
        if self._client:
            from io import BytesIO

            self._client.put_object(
                self.bucket,
                key,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        else:
            path = self._local_root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return f"s3://{self.bucket}/{key}"

    def put_json(self, prefix: str, asset_id: str, filename: str, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(prefix, asset_id, filename, data, "application/json")

    def get_bytes(self, s3_uri: str) -> bytes:
        key = s3_uri.replace(f"s3://{self.bucket}/", "")
        if self._client:
            resp = self._client.get_object(self.bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        return (self._local_root / key).read_bytes()

    def presign(self, s3_uri: str, expires_seconds: int = 300) -> str:
        key = s3_uri.replace(f"s3://{self.bucket}/", "")
        if self._client:
            from datetime import timedelta

            return self._client.presigned_get_object(self.bucket, key, expires=timedelta(seconds=expires_seconds))
        # Local stub URL for demo
        return f"file://{self._local_root / key}?expires={expires_seconds}"

    @staticmethod
    def content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]
