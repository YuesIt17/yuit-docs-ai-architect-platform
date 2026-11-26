"""Phase 3: Flagd/OpenFeature-shaped flags + emergency kill-switch."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


def test_feature_flags_disabled_uses_settings_prompt(seeded):
    seeded.settings.feature_flags_enabled = False
    flags = FeatureFlagService(seeded.settings).evaluate(agent_id="graphrag-chat")
    assert flags.kill_switch is False
    assert flags.prompt_version == seeded.settings.prompt_version
