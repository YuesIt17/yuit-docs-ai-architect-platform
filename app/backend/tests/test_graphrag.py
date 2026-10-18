import pytest

from app.deps import get_container
from app.security.rbac import Principal
from pipelines.seed_all import seed_store


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


def test_hybrid_uses_graph_entities(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("gluten allergen shelf labeling", principal, top_k=5)
    assert hits
    assert any(h.via in {"hybrid", "vector"} for h in hits)
    assert any("allergen" in h.document.text.lower() or h.document.corpus == "policy" for h in hits)


@pytest.mark.asyncio
async def test_chat_agent_returns_citations(seeded):
    c = seeded
    state = await c.agent.arun(
        {
            "request_id": "t2",
            "message": "Что говорит политика про аллергены gluten и nuts?",
            "modality": "chat",
            "role": "store_associate",
            "user_id": "u-assoc",
            "errors": [],
        }
    )
    assert state.get("answer")
    assert state.get("citations")


def test_retrieve_cottage_cheese_not_random_policies(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("Что знаешь про творог?", principal, top_k=5)
    assert hits
    assert all(h.document.doc_id == "sku-cottage-003" or "творог" in h.chunk.text.lower() for h in hits)
    assert not any(h.document.corpus == "policy" and "творог" not in h.chunk.text.lower() for h in hits)


def test_retrieve_unrelated_query_empty(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("квантовая физика чёрных дыр xyzzy", principal, top_k=5)
    assert hits == []


def test_retrieve_cottage_cheese_not_unrelated_policies(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("Что знаешь про творог?", principal, top_k=5)
    assert hits
    assert any(h.document.doc_id == "sku-cottage-003" for h in hits)
    assert all(h.document.corpus == "product" for h in hits)


def test_retrieve_drops_noise_without_lexical_match(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("квантовый телепорт бананов xyzzy", principal, top_k=5)
    assert hits == []
