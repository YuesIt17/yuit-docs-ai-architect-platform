"""GET /v1/graph/subgraph — ACL-filtered demo subgraph from memory seed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kp.deps import get_container
from kp.main import app
from kp.security.rbac import Principal
from pipelines.seed_all import seed_store


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


def test_memory_subgraph_gluten(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    sub = c.store.graph_subgraph("gluten", principal)
    assert sub["nodes"], "seed corpus must expose gluten allergen path"
    assert sub["edges"]
    kinds = {n["kind"] for n in sub["nodes"]}
    assert "entity" in kinds
    assert "document" in kinds
    assert any(e["type"] in ("HAS_ALLERGEN", "GOVERNS") for e in sub["edges"])


def test_subgraph_acl_hides_secret_from_associate(seeded):
    c = seeded
    guestish = Principal(user_id="u-assoc", role="store_associate")
    compliance = Principal(user_id="u-comp", role="compliance_officer")
    sub_a = c.store.graph_subgraph("gluten", guestish, limit=100)
    for n in sub_a["nodes"]:
        if n.get("kind") == "document":
            assert n.get("classification") != "secret"
    sub_c = c.store.graph_subgraph("gluten", compliance, limit=100)
    assert len(sub_c["nodes"]) >= len(sub_a["nodes"])


def test_subgraph_http_endpoint(seeded):
    client = TestClient(app)
    r = client.get(
        "/v1/graph/subgraph",
        params={"seed": "gluten"},
        headers={"Authorization": "Bearer associate"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("seed") == "gluten"
    assert body.get("nodes")
    assert body.get("edges")
