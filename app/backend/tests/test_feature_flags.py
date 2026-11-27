"""Phase 3: Flagd/OpenFeature-shaped flags + emergency kill-switch."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from kp.agent.graph import KnowledgeAgent
from kp.config import get_settings
from kp.deps import get_container
from kp.infrastructure.feature_flags import (
    FLAG_AGENT_ENABLED,
    FLAG_KILL_SWITCH,
    FLAG_MODEL_ROUTE,
    FLAG_PROMPT_VERSION,
    FeatureFlagService,
    default_flags_path,
)
from kp.main import app
from pipelines.seed_all import seed_store

AUTH = {"Authorization": "Bearer compliance"}


@pytest.fixture(autouse=True)
def seeded():
    get_settings.cache_clear()
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    c.flags.clear_overrides()
    yield c
    c.flags.clear_overrides()
    get_settings.cache_clear()
    get_container.cache_clear()


def test_flags_file_ships_with_repo():
    path = default_flags_path()
    assert path.is_file(), f"missing {path}"


def test_default_evaluation_allows_agents(seeded):
    flags = seeded.flags.evaluate(agent_id="graphrag-chat", role="compliance_officer")
    assert flags.kill_switch is False
    assert flags.agent_enabled is True
    assert flags.prompt_version
    assert flags.model_route


def test_kill_switch_blocks_chat_and_audits(seeded):
    seeded.flags.override(FLAG_KILL_SWITCH, True)
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 503, r.text
    assert "kill-switch" in r.json()["detail"].lower() or "kill" in r.json()["detail"].lower()
    assert seeded.store.audit
    row = seeded.store.audit[-1]
    assert row["acl_decision"] == "deny_kill_switch"
    assert row["agent_id"] == "graphrag-chat"


def test_kill_switch_off_restores_chat(seeded):
    seeded.flags.override(FLAG_KILL_SWITCH, True)
    client = TestClient(app)
    assert (
        client.post(
            "/v1/chat",
            headers=AUTH,
            json={"message": "hi", "stream": False},
        ).status_code
        == 503
    )
    seeded.flags.override(FLAG_KILL_SWITCH, False)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text


def test_agent_enabled_false_blocks(seeded):
    seeded.flags.override(FLAG_AGENT_ENABLED, False)
    client = TestClient(app)
    r = client.post(
        "/v1/agents/graphrag-chat/invoke",
        headers=AUTH,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 503


def test_prompt_and_model_route_on_audit(seeded):
    seeded.flags.override(FLAG_PROMPT_VERSION, "v2")
    seeded.flags.override(FLAG_MODEL_ROUTE, "chat-mock")
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text
    row = seeded.store.audit[-1]
    assert row["prompt_version"] == "v2"
    assert row["model_route"] == "chat-mock"
    assert row["flag_variant"][FLAG_PROMPT_VERSION] == "v2"


class _FlagdClient:
    def __init__(self, status_code: int | None = None, exc: Exception | None = None):
        self.status_code = status_code
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        if self.exc is not None:
            raise self.exc

        class _Resp:
            status_code = 503

            def json(self):
                return {"error": "unavailable"}

        _Resp.status_code = self.status_code or 503
        return _Resp()


def test_flagd_timeout_fails_closed_and_audits(seeded, monkeypatch):
    seeded.settings.flagd_url = "http://127.0.0.1:8016"
    monkeypatch.setattr(
        "kp.infrastructure.feature_flags.httpx.Client",
        lambda *args, **kwargs: _FlagdClient(exc=httpx.TimeoutException("timed out")),
    )
    flags = seeded.flags.evaluate(agent_id="graphrag-chat", role="compliance_officer")
    assert flags.provider_status == "flagd_unavailable"
    assert flags.kill_switch is True
    assert flags.agent_enabled is False
    assert flags.model_route == "chat-default"
    assert flags.prompt_version == "v1"

    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 503, r.text
    row = seeded.store.audit[-1]
    assert row["acl_decision"] == "deny_kill_switch"
    assert row["flag_provider"] == "flagd_unavailable"
    assert row["agent_id"] == "graphrag-chat"
    assert "gluten" not in str(row)


def test_flagd_http_error_fails_closed(seeded, monkeypatch):
    seeded.settings.flagd_url = "http://127.0.0.1:8016"
    monkeypatch.setattr(
        "kp.infrastructure.feature_flags.httpx.Client",
        lambda *args, **kwargs: _FlagdClient(status_code=500),
    )
    flags = seeded.flags.evaluate(agent_id="graphrag-chat")
    assert flags.kill_switch is True
    assert flags.agent_enabled is False
    assert flags.provider_status == "flagd_unavailable"


def test_in_memory_defaults_stay_open_without_flagd(seeded):
    assert seeded.settings.flagd_url == ""
    flags = seeded.flags.evaluate(agent_id="graphrag-chat", role="compliance_officer")
    assert flags.provider_status == "in_memory"
    assert flags.kill_switch is False
    assert flags.agent_enabled is True


@pytest.mark.asyncio
async def test_gateway_mock_is_not_a_grounded_success(seeded):
    class _FakeLLM:
        model_uri = "litellm://chat-default"

        async def complete(self, system, user, max_tokens=512, *, model=None):
            return (
                "[gateway-failover] Based on the RetailPartnerX corporate knowledge base.",
                3,
                8,
            )

    agent = KnowledgeAgent(seeded.store, _FakeLLM())
    out = await agent.synthesize(
        {
            "request_id": "r-outage",
            "modality": "chat",
            "role": "compliance_officer",
            "guarded_message": "gluten allergen policy",
            "retrieved": [
                {
                    "doc_id": "pol-1",
                    "classification": "internal",
                    "text": "Gluten policy body",
                }
            ],
            "citations": [
                {
                    "doc_id": "pol-1",
                    "chunk_id": "c1",
                    "corpus": "policy",
                    "classification": "internal",
                    "snippet": "Gluten policy body",
                    "score": 1.0,
                }
            ],
            "model_alias": "chat-default",
        }
    )
    assert out["degraded"] is True
    assert out["citations"] == []
    assert out["acl_decision"] == "degraded_model"
    assert out["answer"].startswith("[degraded:]")
    assert "corporate knowledge base" not in out["answer"].lower()
    assert "Gluten policy body" not in out["answer"]


def test_provider_exception_chat_has_no_citations(seeded):
    async def fake_complete(system, user, max_tokens=512, *, model=None):
        return (
            "[degraded:] The model gateway is unavailable. No grounded answer was produced.",
            0,
            0,
        )

    seeded.llm.complete = fake_complete
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["degraded"] is True
    assert data["citations"] == []
    assert data["answer"].startswith("[degraded:]")
    assert "corporate knowledge" not in data["answer"].lower()
    assert seeded.store.audit[-1]["acl_decision"] == "degraded_model"


def test_feature_flags_disabled_uses_settings_prompt(seeded):
    seeded.settings.feature_flags_enabled = False
    flags = FeatureFlagService(seeded.settings).evaluate(agent_id="graphrag-chat")
    assert flags.kill_switch is False
    assert flags.prompt_version == seeded.settings.prompt_version
