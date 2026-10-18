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


@pytest.mark.asyncio
async def test_category_manager_cannot_see_secret_promo(seeded):
    c = seeded
    mgr = Principal(user_id="u-mgr", role="category_manager")
    hits = c.store.hybrid_retrieve("PrivateLabelX promo margin 42%", mgr, top_k=10)
    assert all(h.document.classification != "secret" for h in hits)


@pytest.mark.asyncio
async def test_compliance_can_see_secret(seeded):
    c = seeded
    officer = Principal(user_id="u-comp", role="compliance_officer")
    hits = c.store.hybrid_retrieve("PrivateLabelX promo margin", officer, top_k=10)
    assert any(h.document.classification == "secret" for h in hits)


@pytest.mark.asyncio
async def test_agent_denies_secret_to_manager(seeded):
    c = seeded
    state = await c.agent.arun(
        {
            "request_id": "t1",
            "message": "Расскажи про Q4 Closed Promo Margin Playbook и маржу 42%",
            "modality": "chat",
            "role": "category_manager",
            "user_id": "u-mgr",
            "errors": [],
        }
    )
    # Either no secret citations or empty/insufficient — never leak secret text
    for cit in state.get("citations") or []:
        assert cit["classification"] != "secret"
    assert "42%" not in (state.get("answer") or "") or state.get("acl_decision") == "deny_output"
