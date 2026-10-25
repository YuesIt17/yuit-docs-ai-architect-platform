"""RAG-03: graph-on vs graph-off and edge deletion impact."""

from __future__ import annotations

import pytest

from kp.deps import get_container
from kp.security.rbac import Principal
from pipelines.seed_all import seed_store


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


def test_graph_on_finds_policy_via_allergen(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    c.store._enable_graph_resolve = True
    graph_ids = c.store.graph_resolve_doc_ids("gluten", principal)
    assert graph_ids, "graph resolve must find docs for gluten"
    hits = c.store.hybrid_retrieve("gluten", principal, top_k=5, graph_doc_ids=graph_ids)
    assert hits
    assert any(h.via == "hybrid" or h.document.corpus in {"policy", "product"} for h in hits)


def test_graph_off_is_vector_only_path(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    c.store._enable_graph_resolve = False
    assert c.store.graph_resolve_doc_ids("gluten", principal) == []
    hits = c.store.hybrid_retrieve("gluten allergen shelf labeling", principal, top_k=5, vector_only=True)
    # Vector-only may still find lexical overlap — but must not claim graph via alone as proof.
    assert all(h.via in {"vector", "hybrid"} for h in hits)


def test_graph_contribution_not_vector_alone(seeded):
    """Regression: vector-only success is not proof of GraphRAG."""
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    c.store._enable_graph_resolve = True
    graph_ids = c.store.graph_resolve_doc_ids("gluten nuts milk labeling", principal)
    assert graph_ids
    on_hits = c.store.hybrid_retrieve(
        "gluten nuts milk labeling", principal, top_k=5, graph_doc_ids=graph_ids
    )
    assert any(h.via == "hybrid" for h in on_hits) or any(
        h.document.doc_id in graph_ids for h in on_hits
    )


def test_removing_governs_edge_changes_resolve(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    before = set(c.store.graph_resolve_doc_ids("gluten", principal))
    assert before
    # Drop GOVERNS / HAS_ALLERGEN edges for gluten entity
    gluten = next(e for e in c.store.entities.values() if e.name.lower() == "gluten")
    c.store._memory.edges = [
        e
        for e in c.store._memory.edges
        if not (e[2] == gluten.entity_id and e[1] in {"HAS_ALLERGEN", "GOVERNS"})
    ]
    gluten.linked_doc_ids = []
    after = set(c.store.graph_resolve_doc_ids("gluten", principal))
    assert after != before or not after


def test_secret_branch_hidden_from_manager_in_graph(seeded):
    c = seeded
    mgr = Principal(user_id="u-mgr", role="category_manager")
    ids = c.store.graph_resolve_doc_ids("PrivateLabelX promo margin", mgr)
    for doc_id in ids:
        doc = c.store.documents[doc_id]
        assert doc.classification != "secret"
