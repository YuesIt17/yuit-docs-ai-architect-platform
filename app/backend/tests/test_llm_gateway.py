"""Phase 2: LiteLLM gateway-local client path and metering attribution."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kp.config import Settings, get_settings
from kp.deps import get_container
from kp.infrastructure.llm import LLMClient, gateway_mode, litellm_endpoint
from kp.main import app
from pipelines.seed_all import seed_store

AUTH = {"Authorization": "Bearer compliance"}


@pytest.fixture(autouse=True)
def reset_singletons():
    get_settings.cache_clear()
    get_container.cache_clear()
    yield
    get_settings.cache_clear()
    get_container.cache_clear()


def test_gateway_mode_default_is_direct():
    settings = Settings()
    assert gateway_mode(settings) == "direct"
    cfg = LLMClient(settings).get_config()
    assert cfg.provider == "MOCK"
    assert cfg.gateway == "direct"


def test_gateway_litellm_binds_alias_and_url():
    settings = Settings(
        llm_gateway="litellm",
        litellm_base_url="http://127.0.0.1:4000/v1",
        litellm_model_alias="chat-default",
        litellm_api_key="sk-kp-local-gateway",
    )
    assert gateway_mode(settings) == "litellm"
    cfg = LLMClient(settings).get_config()
    assert cfg.provider == "LITELLM"
    assert cfg.gateway == "litellm"
    assert cfg.base_url == "http://127.0.0.1:4000/v1"
    assert cfg.model == "chat-default"
    assert cfg.model_uri == "litellm://chat-default"


def test_set_model_alias_for_flag_route():
    settings = Settings(llm_gateway="litellm", litellm_base_url="http://127.0.0.1:4000/v1")
    client = LLMClient(settings)
    client.set_model_alias("chat-mock")
    assert client.get_config().model == "chat-mock"


def test_litellm_endpoint_helpers():
    settings = Settings(litellm_base_url="", litellm_model_alias="")
    url, alias = litellm_endpoint(settings)
    assert url.endswith(":4000/v1")
    assert alias == "chat-default"


def test_apply_config_litellm_allowlisted():
    settings = Settings(
        llm_allowed_base_urls="http://127.0.0.1:4000/v1",
        litellm_api_key="sk-test",
    )
    client = LLMClient(settings)
    cfg = client.apply_config("LITELLM", "http://127.0.0.1:4000/v1", "chat-mock")
    assert cfg.provider == "LITELLM"
    assert cfg.model == "chat-mock"
    assert cfg.gateway == "litellm"


def test_chat_audit_includes_gateway_attribution(monkeypatch):
    monkeypatch.setenv("LLM_GATEWAY", "direct")
    get_settings.cache_clear()
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text
    assert c.store.audit, "expected an audit row"
    row = c.store.audit[-1]
    assert row["agent_id"] == "graphrag-chat"
    assert row["team_id"] == c.settings.llm_team_id
    assert row["gateway"] == "direct"
    assert row.get("model_route")
    assert row.get("prompt_version")
