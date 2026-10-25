"""SEC-04: demo-auth flag and LLM URL allowlist."""

from __future__ import annotations

import pytest

from kp.config import Settings
from kp.infrastructure.llm import LLMClient
from kp.security.rbac import AuthDisabledError, LLM_ADMIN_ROLES, resolve_principal


def test_demo_auth_disabled_rejects():
    with pytest.raises(AuthDisabledError):
        resolve_principal("manager", demo_auth_enabled=False)
    with pytest.raises(AuthDisabledError):
        resolve_principal(None, demo_auth_enabled=False)


def test_llm_rejects_arbitrary_url():
    settings = Settings(
        llm_provider="OLLAMA",
        openai_base_url="http://127.0.0.1:11434/v1",
        llm_allow_runtime_url_override=False,
        llm_allowed_base_urls="http://127.0.0.1:11434/v1,http://localhost:11434/v1",
    )
    client = LLMClient(settings)
    with pytest.raises(ValueError, match="allowlist"):
        client.apply_config("OLLAMA", "http://evil.example:9999/v1", "qwen2.5:0.5b")


def test_llm_accepts_allowlisted_url():
    settings = Settings(
        llm_provider="MOCK",
        openai_base_url="http://127.0.0.1:11434/v1",
        llm_allow_runtime_url_override=False,
        llm_allowed_base_urls="http://127.0.0.1:11434/v1,http://host.docker.internal:11434/v1",
    )
    client = LLMClient(settings)
    cfg = client.apply_config("OLLAMA", "http://host.docker.internal:11434/v1", "qwen2.5:0.5b")
    assert "host.docker.internal" in cfg.base_url
    assert cfg.provider == "OLLAMA"


def test_only_compliance_is_llm_admin():
    assert "category_manager" not in LLM_ADMIN_ROLES
    assert "compliance_officer" in LLM_ADMIN_ROLES
