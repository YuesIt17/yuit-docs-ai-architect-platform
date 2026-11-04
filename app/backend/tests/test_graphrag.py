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


def test_hybrid_uses_graph_entities(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    graph_ids = c.store.graph_resolve_doc_ids("gluten allergen shelf labeling", principal)
    assert graph_ids, "GraphRAG requires a non-empty graph resolve path"
    hits = c.store.hybrid_retrieve(
        "gluten allergen shelf labeling", principal, top_k=5, graph_doc_ids=graph_ids
    )
    assert hits
    assert any(h.via == "hybrid" or h.document.doc_id in graph_ids for h in hits)
    assert any("allergen" in h.document.text.lower() or h.document.corpus == "policy" for h in hits)


@pytest.mark.asyncio
async def test_chat_agent_returns_citations(seeded):
    c = seeded
    state = await c.agent.arun(
        {
            "request_id": "t2",
            "message": "What does the policy say about gluten and nuts allergens?",
            "modality": "chat",
            "role": "store_associate",
            "user_id": "u-assoc",
            "errors": [],
        }
    )
    assert state.get("answer")
    assert state.get("citations")


@pytest.mark.asyncio
async def test_labeling_question_is_answered_as_chat(seeded):
    state = await seeded.agent.arun(
        {
            "request_id": "t-labeling",
            "message": "Which labeling policies relate to gluten?",
            "modality": "chat",
            "role": "store_associate",
            "user_id": "u-assoc",
            "errors": [],
        }
    )
    assert state["route"] == "chat"
    assert state.get("citations")


@pytest.mark.asyncio
async def test_off_topic_question_is_refused_after_refine(seeded):
    state = await seeded.agent.arun(
        {
            "request_id": "t-off-topic",
            "message": "quantum physics of black holes xyzzy",
            "modality": "chat",
            "role": "store_associate",
            "user_id": "u-assoc",
            "errors": [],
        }
    )
    assert state["refine_count"] == 1
    assert state["citations"] == []
    assert state["answer"].startswith("Insufficient relevant context")


def test_retrieve_cottage_cheese_not_random_policies(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("What do you know about cottage cheese?", principal, top_k=5)
    assert hits
    assert all(h.document.doc_id == "sku-cottage-003" or "cottage cheese" in h.chunk.text.lower() for h in hits)
    assert not any(h.document.corpus == "policy" and "cottage cheese" not in h.chunk.text.lower() for h in hits)


def test_retrieve_unrelated_query_empty(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("quantum physics of black holes xyzzy", principal, top_k=5)
    assert hits == []


def test_retrieve_cottage_cheese_not_unrelated_policies(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("What do you know about cottage cheese?", principal, top_k=5)
    assert hits
    assert any(h.document.doc_id == "sku-cottage-003" for h in hits)
    assert all(h.document.corpus == "product" for h in hits)


def test_retrieve_drops_noise_without_lexical_match(seeded):
    c = seeded
    principal = Principal(user_id="u-assoc", role="store_associate")
    hits = c.store.hybrid_retrieve("quantum banana teleporter xyzzy", principal, top_k=5)
    assert hits == []
