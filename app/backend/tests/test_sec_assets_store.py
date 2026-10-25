"""SEC-02 / SEC-03: asset ACL and object-store path safety."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from kp.api.vision import presign_asset
from kp.config import Settings
from kp.deps import get_container
from kp.domain.nodes import LabelAssetNode
from kp.infrastructure.object_store import ObjectStore, ObjectStoreError
from kp.security.rbac import Principal, resolve_principal
from pipelines.seed_all import seed_store


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


@pytest.mark.asyncio
async def test_guest_cannot_presign_internal_asset(seeded, tmp_path):
    c = seeded
    asset_id = "asset-internal-demo"
    c.store.add_label_asset(
        LabelAssetNode(
            asset_id=asset_id,
            source_format="png",
            page_count=1,
            classification="internal",
            allowed_roles=["store_associate", "category_manager", "compliance_officer"],
            s3_uri_raw=f"s3://{c.settings.minio_bucket}/raw/{asset_id}/x.png",
            s3_uri_recognized=f"s3://{c.settings.minio_bucket}/recognized/{asset_id}/extract.json",
            s3_uri_normalized=f"s3://{c.settings.minio_bucket}/normalized/{asset_id}/",
            etag="abc",
        )
    )
    guest = resolve_principal("guest")
    with pytest.raises(HTTPException) as ei:
        await presign_asset(asset_id, kind="recognized", principal=guest, c=c)
    assert ei.value.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_presign_secret_asset(seeded):
    c = seeded
    asset_id = "asset-secret-demo"
    c.store.add_label_asset(
        LabelAssetNode(
            asset_id=asset_id,
            source_format="png",
            page_count=1,
            classification="secret",
            allowed_roles=["compliance_officer"],
            s3_uri_raw=f"s3://{c.settings.minio_bucket}/raw/{asset_id}/x.png",
            s3_uri_recognized=f"s3://{c.settings.minio_bucket}/recognized/{asset_id}/extract.json",
            s3_uri_normalized=f"s3://{c.settings.minio_bucket}/normalized/{asset_id}/",
            etag="abc",
        )
    )
    mgr = Principal(user_id="u-mgr", role="category_manager")
    with pytest.raises(HTTPException) as ei:
        await presign_asset(asset_id, kind="raw", principal=mgr, c=c)
    assert ei.value.status_code == 403

    compliance = Principal(user_id="u-comp", role="compliance_officer")
    # Will fail on missing object bytes for presign path resolution — create file first
    store = ObjectStore(c.settings, local_root=Path(c.settings.minio_bucket and "") or None)
    # Use container object store with safe write
    name = ObjectStore.safe_storage_name("x.png")
    c.object_store.put_bytes("recognized", asset_id, name, b'{"ok":true}', "application/json")
    # Update URI to match written key
    asset = c.store.labels[asset_id]
    asset.s3_uri_recognized = f"s3://{c.settings.minio_bucket}/recognized/{asset_id}/{name}"
    resp = await presign_asset(asset_id, kind="recognized", principal=compliance, c=c)
    assert resp.expires_seconds == 300
    assert resp.url


def test_object_store_rejects_traversal(tmp_path):
    settings = Settings(store_backend="memory", minio_bucket="test-bucket")
    store = ObjectStore(settings, local_root=tmp_path)
    with pytest.raises(ObjectStoreError):
        store.put_bytes("raw", "aid", "../escape.png", b"x", "image/png")
    with pytest.raises(ObjectStoreError):
        store.put_bytes("raw", "aid", "..", b"x", "image/png")
    name = ObjectStore.safe_storage_name("../../etc/passwd.png")
    assert ".." not in name
    uri = store.put_bytes("raw", "aid", name, b"hello", "image/png")
    assert (tmp_path / "raw" / "aid" / name).is_file()
    assert store.get_bytes(uri) == b"hello"


def test_safe_storage_name_ignores_absolute_paths():
    name = ObjectStore.safe_storage_name(r"C:\Windows\System32\evil.png")
    assert name.endswith(".png")
    assert "Windows" not in name
    assert "\\" not in name
    assert "/" not in name
