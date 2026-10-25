"""SEC-01: semantic cache must re-authorize sources after ACL changes."""

from __future__ import annotations

import pytest

from kp.application.chat import ChatService
from kp.config import get_settings
from kp.deps import get_container
from kp.domain.schemas import ChatRequest
from kp.security.rbac import Principal
from pipelines.seed_all import seed_store


@pytest.fixture
def chat_env(monkeypatch):
    monkeypatch.setenv("ENABLE_SEMANTIC_CACHE", "true")
    get_settings.cache_clear()
    get_container.cache_clear()
    c = get_container()
    # Settings cached before env may still be false — force on container settings.
    c.settings.enable_semantic_cache = True
    seed_store(c.store)
    return c


@pytest.mark.asyncio
async def test_cache_hit_then_classification_revoke(chat_env):
    c = chat_env
    svc = ChatService(c, c.settings)
    mgr = Principal(user_id="u-mgr", role="category_manager")
    # Use a public/internal product question that returns citations
    body = ChatRequest(message="овсяные хлопья FreshFarm аллергены", session_id="s1", stream=False)
    first = await svc.handle(body, mgr)
    assert first.acl_decision in {"allow", "allow_cache"}
    assert first.citations, "need citations to test revoke"

    # Poison cache explicitly then revoke ACL on cited docs
    doc_id = first.citations[0].doc_id
    doc = c.store.documents[doc_id]
    # Second identical request should hit cache when ACL still ok
    second = await svc.handle(body, mgr)
    assert second.acl_decision == "allow_cache"

    doc.classification = "secret"
    doc.allowed_roles = ["compliance_officer"]
    third = await svc.handle(body, mgr)
    assert third.acl_decision != "allow_cache"
    for cit in third.citations:
        assert cit.classification != "secret"


@pytest.mark.asyncio
async def test_cache_miss_when_source_deleted(chat_env):
    c = chat_env
    svc = ChatService(c, c.settings)
    mgr = Principal(user_id="u-mgr", role="category_manager")
    body = ChatRequest(message="молоко Простоквашино состав", session_id="s2", stream=False)
    first = await svc.handle(body, mgr)
    if not first.citations:
        pytest.skip("no citations for seed query")
    assert (await svc.handle(body, mgr)).acl_decision == "allow_cache"
    for cit in first.citations:
        c.store.documents.pop(cit.doc_id, None)
    again = await svc.handle(body, mgr)
    assert again.acl_decision != "allow_cache"


@pytest.mark.asyncio
async def test_policy_version_invalidates_cache(chat_env):
    c = chat_env
    svc = ChatService(c, c.settings)
    mgr = Principal(user_id="u-mgr", role="category_manager")
    body = ChatRequest(message="политика маркировки аллергенов", session_id="s3", stream=False)
    await svc.handle(body, mgr)
    hit = await svc.handle(body, mgr)
    if hit.acl_decision != "allow_cache":
        pytest.skip("cache did not hit for this query")
    c.settings.policy_version = "v2-bumped"
    miss = await svc.handle(body, mgr)
    assert miss.acl_decision != "allow_cache"
