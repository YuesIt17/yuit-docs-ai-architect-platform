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
