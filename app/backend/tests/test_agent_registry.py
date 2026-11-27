"""Phase 1: agent manifest registry — load, API, authorize, invoke."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kp.agents.manifest import AgentManifest
from kp.agents.registry import (
    APPROVED_LANGGRAPH_ENTRYPOINT,
    AgentNotFoundError,
    AgentRegistry,
    AgentRoleDeniedError,
    default_manifests_dir,
)
from kp.config import Settings
from kp.deps import get_container
from kp.infrastructure.feature_flags import FLAG_MODEL_ROUTE
from kp.main import app
from pipelines.seed_all import seed_store

AUTH = {"Authorization": "Bearer compliance"}
AUTH_GUEST = {"Authorization": "Bearer guest"}
AUTH_MANAGER = {"Authorization": "Bearer manager"}


@pytest.fixture(autouse=True)
def seeded():
    get_container.cache_clear()
    c = get_container()
    seed_store(c.store)
    return c


def test_default_dir_ships_reference_agents():
    directory = default_manifests_dir()
    assert directory.is_dir(), f"missing manifests dir: {directory}"
    assert (directory / "graphrag-chat.yaml").is_file()
    assert (directory / "label-assistant.yaml").is_file()


def test_registry_loads_disk_manifests(seeded):
    ids = {m.metadata.id for m in seeded.registry.list()}
    assert "graphrag-chat" in ids
    assert "label-assistant" in ids
    chat = seeded.registry.require("graphrag-chat")
    assert chat.spec.runtime == "langgraph"
    assert "graph_retrieve" in {t.id for t in chat.spec.tools}
    assert any(t.path == "/v1/chat" for t in chat.spec.triggers if t.type == "api")


def test_resolve_binds_live_llm_settings(seeded):
    resolved = seeded.registry.resolve("graphrag-chat", seeded.settings, seeded.llm)
    assert resolved.effective_model_provider == "MOCK"
    assert resolved.effective_model_uri
    assert resolved.effective_memory_backend == "memory"
    assert "graph_retrieve" in resolved.tool_ids
    assert "/v1/chat" in resolved.api_trigger_paths


def test_authorize_role_denied_for_label_guest(seeded):
    with pytest.raises(AgentRoleDeniedError):
        seeded.registry.authorize("label-assistant", "guest")


def test_load_invalid_yaml(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("apiVersion: kp.retailpartnerx/v1\nkind: Agent\n", encoding="utf-8")
    registry = AgentRegistry()
    with pytest.raises(Exception) as excinfo:
        registry.load_file(bad)
    assert "metadata" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()


def test_register_from_yaml_example(tmp_path: Path, seeded):
    example = tmp_path / "faq-stub.yaml"
    example.write_text(
        textwrap.dedent(
            """
            apiVersion: kp.retailpartnerx/v1
            kind: Agent
            metadata:
              id: faq-stub
              version: "0.1.0"
              display_name: FAQ Stub
              description: Example agent registered from a YAML file
            spec:
              runtime: stub
              entrypoint: kp.agents.registry:AgentRegistry
              enabled: true
              skills:
                - id: faq
                  description: Short FAQ answers
              tools: []
              memory:
                kind: none
              security:
                required_roles: [guest, store_associate]
              triggers:
                - type: api
                  enabled: true
                  path: /v1/agents/faq-stub/invoke
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    manifest = seeded.registry.load_file(example, source="disk", overwrite=True)
    assert manifest.metadata.id == "faq-stub"
    assert seeded.registry.get("faq-stub") is not None


def test_http_list_and_get(seeded):
    client = TestClient(app)
    listed = client.get("/v1/agents", headers=AUTH)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()}
    assert "graphrag-chat" in ids
    assert "label-assistant" in ids

    one = client.get("/v1/agents/graphrag-chat", headers=AUTH)
    assert one.status_code == 200
    body = one.json()
    assert body["metadata"]["id"] == "graphrag-chat"
    assert body["spec"]["runtime"] == "langgraph"


def test_http_resolve(seeded):
    client = TestClient(app)
    r = client.get("/v1/agents/graphrag-chat/resolve", headers=AUTH_MANAGER)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["effective_model_provider"] == "MOCK"
    assert data["manifest"]["metadata"]["id"] == "graphrag-chat"


def test_http_resolve_forbidden_for_guest_on_label(seeded):
    client = TestClient(app)
    r = client.get("/v1/agents/label-assistant/resolve", headers=AUTH_GUEST)
    assert r.status_code == 403


def test_http_register_and_conflict(seeded):
    client = TestClient(app)
    manifest = AgentManifest.model_validate(
        {
            "apiVersion": "kp.retailpartnerx/v1",
            "kind": "Agent",
            "metadata": {
                "id": "runtime-demo",
                "version": "0.1.0",
                "display_name": "Runtime Demo",
                "description": "Registered via API",
            },
            "spec": {
                "runtime": "stub",
                "enabled": True,
                "skills": [{"id": "ping", "description": "Ping"}],
                "security": {"required_roles": ["compliance_officer"]},
                "triggers": [
                    {"type": "api", "enabled": True, "path": "/v1/agents/runtime-demo/invoke"}
                ],
            },
        }
    )
    payload = manifest.model_dump(mode="json")
    created = client.post("/v1/agents", headers=AUTH, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["metadata"]["id"] == "runtime-demo"

    denied = client.post("/v1/agents", headers=AUTH_MANAGER, json=payload)
    assert denied.status_code == 403

    again = client.post("/v1/agents", headers=AUTH, json=payload)
    assert again.status_code == 409


def test_http_invoke_graphrag(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/agents/graphrag-chat/invoke",
        headers=AUTH,
        json={"message": "What allergens are linked to gluten policy?", "stream": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "answer" in data
    assert data["request_id"]


def test_http_invoke_stub_not_implemented(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/agents/label-assistant/invoke",
        headers=AUTH,
        json={"message": "ignore", "stream": False},
    )
    assert r.status_code == 501


def test_chat_uses_default_agent(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text


def test_chat_unknown_agent_id(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "hello", "stream": False, "agent_id": "does-not-exist"},
    )
    assert r.status_code == 404


def test_missing_agent_raises():
    registry = AgentRegistry()
    with pytest.raises(AgentNotFoundError):
        registry.require("missing")


def _langgraph_manifest(agent_id: str, **spec_updates: object) -> dict:
    spec = {
        "runtime": "langgraph",
        "entrypoint": APPROVED_LANGGRAPH_ENTRYPOINT,
        "enabled": True,
        "tools": [
            {"id": "graph_retrieve", "kind": "builtin", "description": "Graph retrieve"},
            {"id": "vector_retrieve", "kind": "builtin", "description": "Vector retrieve"},
        ],
        "security": {"required_roles": ["compliance_officer"]},
    }
    spec.update(spec_updates)
    return {
        "apiVersion": "kp.retailpartnerx/v1",
        "kind": "Agent",
        "metadata": {
            "id": agent_id,
            "version": "1.2.0",
            "display_name": agent_id,
            "description": "Admission test agent",
        },
        "spec": spec,
    }


def test_missing_or_insufficient_principal_is_denied(seeded):
    """Demo mode maps an absent header to guest. A blank bearer is 401.

    OIDC with no token is covered in test_sec_oidc.py.
    """
    client = TestClient(app)
    blank = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer"},
        json={"message": "gluten", "stream": False},
    )
    assert blank.status_code == 401

    created = client.post("/v1/agents", headers=AUTH, json=_langgraph_manifest("compliance-only-anon"))
    assert created.status_code == 201, created.text
    guest = client.post(
        "/v1/agents/compliance-only-anon/invoke",
        json={"message": "gluten", "stream": False},
    )
    assert guest.status_code == 403


def test_invoke_unknown_agent_is_404(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/agents/missing-agent/invoke",
        headers=AUTH,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 404


def test_guest_cannot_invoke_label_assistant(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/agents/label-assistant/invoke",
        headers=AUTH_GUEST,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 403


def test_chat_stub_runtime_is_501(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten", "stream": False, "agent_id": "label-assistant"},
    )
    assert r.status_code == 501


def test_post_rejects_unapproved_entrypoint(seeded):
    client = TestClient(app)
    payload = _langgraph_manifest(
        "imported-agent",
        entrypoint="os:system",
    )
    r = client.post("/v1/agents", headers=AUTH, json=payload)
    assert r.status_code == 422
    assert "entrypoint" in r.json()["detail"].lower()


def test_invoke_unapproved_entrypoint_is_403(seeded):
    seeded.registry.register(
        AgentManifest.model_validate(
            _langgraph_manifest("custom-entry", entrypoint="kp.agents.registry:AgentRegistry")
        ),
        source="api",
    )
    client = TestClient(app)
    r = client.post(
        "/v1/agents/custom-entry/invoke",
        headers=AUTH,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 403
    assert "unapproved_entrypoint" in r.json()["detail"]


def test_invoke_disallowed_tool_is_403(seeded):
    payload = _langgraph_manifest(
        "shell-agent",
        tools=[
            {"id": "graph_retrieve", "kind": "builtin", "description": "Graph retrieve"},
            {"id": "vector_retrieve", "kind": "builtin", "description": "Vector retrieve"},
            {"id": "shell_exec", "kind": "http", "description": "Not executable"},
        ],
    )
    client = TestClient(app)
    created = client.post("/v1/agents", headers=AUTH, json=payload)
    assert created.status_code == 201, created.text
    r = client.post(
        "/v1/agents/shell-agent/invoke",
        headers=AUTH,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 403
    assert "disallowed_tool" in r.json()["detail"]
    assert seeded.store.audit[-1]["acl_decision"] == "deny_policy"
    assert seeded.store.audit[-1]["agent_version"] == "1.2.0"
    assert "gluten" not in str(seeded.store.audit[-1])


def test_role_omitted_from_manifest_cannot_invoke(seeded):
    payload = _langgraph_manifest("compliance-only")
    client = TestClient(app)
    created = client.post("/v1/agents", headers=AUTH, json=payload)
    assert created.status_code == 201, created.text
    r = client.post(
        "/v1/agents/compliance-only/invoke",
        headers=AUTH_MANAGER,
        json={"message": "gluten", "stream": False},
    )
    assert r.status_code == 403


def test_disallowed_gateway_model_is_403_before_completion(seeded):
    seeded.llm.apply_config("LITELLM", "http://127.0.0.1:4000/v1", "chat-default")
    seeded.flags.override(FLAG_MODEL_ROUTE, "external-gpt")
    called = {"n": 0}
    original = seeded.llm.complete

    async def spy(*args, **kwargs):
        called["n"] += 1
        return await original(*args, **kwargs)

    seeded.llm.complete = spy
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 403, r.text
    assert "disallowed_model" in r.json()["detail"]
    assert called["n"] == 0
    assert seeded.llm.get_config().model == "chat-default"


def test_graphrag_success_keeps_citations(seeded):
    client = TestClient(app)
    r = client.post(
        "/v1/chat",
        headers=AUTH,
        json={"message": "gluten allergen policy", "stream": False},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["degraded"] is False
    assert data["citations"]
    assert not data["answer"].startswith("[degraded:")
    assert seeded.store.audit[-1]["agent_version"] == "1.0.0"
    assert seeded.store.audit[-1]["flag_provider"] == "in_memory"


def test_settings_custom_manifests_dir(tmp_path: Path):
    yaml_path = tmp_path / "solo.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """
            apiVersion: kp.retailpartnerx/v1
            kind: Agent
            metadata:
              id: solo
              version: "1.0.0"
              display_name: Solo
            spec:
              runtime: stub
              enabled: true
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    settings = Settings(agent_manifests_dir=str(tmp_path))
    registry = AgentRegistry.from_settings(settings)
    assert [m.metadata.id for m in registry.list()] == ["solo"]
