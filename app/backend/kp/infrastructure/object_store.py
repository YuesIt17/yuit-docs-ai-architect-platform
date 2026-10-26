"""MinIO / local filesystem S3-compatible object store."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from kp.config import Settings

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,180}$")


class ObjectStoreError(ValueError):
    """Raised when an object key would escape the store root or is unsafe."""


def _default_object_store_root(bucket: str) -> Path:
    """Local FS fallback root for monorepo checkout and container image.

    Dev:  ``.../app/backend/kp/infrastructure/`` → ``<repo>/data/object-store/<bucket>``
    Image: ``/app/kp/infrastructure/`` → ``/app/data/object-store/<bucket>``
    (Docker layout is flatter — ``parents[4]`` does not exist and used to crash startup.)
    """
    here = Path(__file__).resolve()
    # parents[0]=infrastructure, [1]=kp, [2]=backend|/app
    install_root = here.parents[2]
    if install_root.name == "backend" and len(here.parents) > 4:
        return here.parents[4] / "data" / "object-store" / bucket
    return install_root / "data" / "object-store" / bucket


class ObjectStore:
    """Stores raw + recognized artifacts. Uses local FS when MinIO unavailable."""

    def __init__(self, settings: Settings, local_root: Path | None = None):
        self.settings = settings
        self.bucket = settings.minio_bucket
        self._local_root = local_root if local_root is not None else _default_object_store_root(self.bucket)
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

    @staticmethod
    def safe_storage_name(original_filename: str | None, *, default_ext: str = "bin") -> str:
        """Generate a server-side storage basename; never trust client paths."""
        raw = (original_filename or "").replace("\\", "/").split("/")[-1]
        ext = ""
        if "." in raw:
            candidate = raw.rsplit(".", 1)[-1].lower()
            if candidate.isalnum() and len(candidate) <= 8:
                ext = candidate
        if not ext:
            ext = default_ext
        return f"{uuid.uuid4().hex}.{ext}"

    def _assert_safe_components(self, *parts: str) -> None:
        for part in parts:
            if not part or part in {".", ".."}:
                raise ObjectStoreError(f"unsafe path component: {part!r}")
            if "/" in part or "\\" in part or "\x00" in part:
                raise ObjectStoreError(f"unsafe path component: {part!r}")
            if not _SAFE_NAME.match(part):
                raise ObjectStoreError(f"unsafe path component: {part!r}")

    def _key(self, prefix: str, asset_id: str, filename: str) -> str:
        self._assert_safe_components(prefix, asset_id, filename)
        return f"{prefix}/{asset_id}/{filename}"

    def _resolve_local(self, key: str) -> Path:
        """Resolve key under local root; reject traversal / symlink escape."""
        root = self._local_root.resolve()
        path = (root / key).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ObjectStoreError("path escapes object-store root") from exc
        return path

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
            path = self._resolve_local(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return f"s3://{self.bucket}/{key}"

    def put_json(self, prefix: str, asset_id: str, filename: str, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(prefix, asset_id, filename, data, "application/json")

    def get_bytes(self, s3_uri: str) -> bytes:
        key = s3_uri.replace(f"s3://{self.bucket}/", "")
        self._assert_safe_components(*key.split("/"))
        if self._client:
            resp = self._client.get_object(self.bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        return self._resolve_local(key).read_bytes()

    def presign(self, s3_uri: str, expires_seconds: int = 300) -> str:
        key = s3_uri.replace(f"s3://{self.bucket}/", "")
        self._assert_safe_components(*key.split("/"))
        if self._client:
            from datetime import timedelta

            return self._client.presigned_get_object(
                self.bucket, key, expires=timedelta(seconds=expires_seconds)
            )
        path = self._resolve_local(key)
        return f"file://{path}?expires={expires_seconds}"

    @staticmethod
    def content_hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:16]
