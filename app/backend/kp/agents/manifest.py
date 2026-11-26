"""Pydantic schema for the declarative Agent manifest (ADR-011)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AgentSkill(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str = Field(max_length=500)


class AgentTool(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    kind: Literal["builtin", "mcp", "http"] = "builtin"
    description: str = Field(default="", max_length=500)
    # MCP / HTTP refs are declarative for now; runtime wiring lands in later phases.
    ref: str | None = Field(default=None, max_length=256)


class AgentMemorySpec(BaseModel):
    kind: Literal["none", "langgraph_checkpoint"] = "langgraph_checkpoint"
    # "settings" follows SESSION_BACKEND / STORE_BACKEND; otherwise an explicit backend.
    backend: Literal["settings", "memory", "postgres"] = "settings"


class AgentModelSpec(BaseModel):
    # "settings" binds to the live LLMClient (MOCK / Ollama / vLLM).
    provider_ref: Literal["settings"] = "settings"
    alias: str = Field(default="chat-default", max_length=64)
    prompt_version_ref: Literal["settings"] = "settings"


class AgentGuardrailsSpec(BaseModel):
    input: bool = True
    output: bool = True
    acl: Literal["role_based"] = "role_based"


class AgentSandboxSpec(BaseModel):
    network: Literal["deny_egress_except_llm_store", "cluster_default"] = "deny_egress_except_llm_store"
    tool_allowlist: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, ge=1, le=600)


class AgentSecuritySpec(BaseModel):
    required_roles: list[
        Literal["guest", "store_associate", "category_manager", "compliance_officer"]
    ] = Field(
        default_factory=lambda: [
            "guest",
            "store_associate",
            "category_manager",
            "compliance_officer",
        ]
    )
    classifications: list[Literal["public", "internal", "secret"]] = Field(
        default_factory=lambda: ["public", "internal", "secret"]
    )


class AgentTrigger(BaseModel):
    type: Literal["api", "a2a", "schedule"]
    enabled: bool = True
    path: str | None = Field(default=None, max_length=128)
    note: str = Field(default="", max_length=250)


class AgentSpec(BaseModel):
    runtime: Literal["langgraph", "adk", "stub"] = "langgraph"
    entrypoint: str = Field(
        default="kp.agent.graph:KnowledgeAgent",
        max_length=256,
        description="Python import path for the runtime binding",
    )
    enabled: bool = True
    skills: list[AgentSkill] = Field(default_factory=list)
    tools: list[AgentTool] = Field(default_factory=list)
    memory: AgentMemorySpec = Field(default_factory=AgentMemorySpec)
    model: AgentModelSpec = Field(default_factory=AgentModelSpec)
    guardrails: AgentGuardrailsSpec = Field(default_factory=AgentGuardrailsSpec)
    sandbox: AgentSandboxSpec = Field(default_factory=AgentSandboxSpec)
    security: AgentSecuritySpec = Field(default_factory=AgentSecuritySpec)
    triggers: list[AgentTrigger] = Field(default_factory=list)


class AgentMetadata(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]*$")
    version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+(\.[0-9]+){0,2}$")
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("labels")
    @classmethod
    def _label_budget(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 16:
            raise ValueError("at most 16 labels")
        for key, raw in value.items():
            if len(key) > 63 or len(raw) > 63:
                raise ValueError("label keys and values must be ≤63 characters")
        return value


class AgentManifest(BaseModel):
    """Single declarative specification that registers an agent on the platform."""

    apiVersion: Literal["kp.retailpartnerx/v1"] = "kp.retailpartnerx/v1"
    kind: Literal["Agent"] = "Agent"
    metadata: AgentMetadata
    spec: AgentSpec

    @property
    def id(self) -> str:
        return self.metadata.id


class ResolvedAgent(BaseModel):
    """Manifest plus runtime bindings resolved from live settings / LLM client."""

    manifest: AgentManifest
    effective_model_provider: str
    effective_model: str
    effective_model_uri: str
    effective_prompt_version: str
    effective_memory_backend: str
    tool_ids: list[str] = Field(default_factory=list)
    api_trigger_paths: list[str] = Field(default_factory=list)
    source: Literal["disk", "api"] = "disk"
    extras: dict[str, Any] = Field(default_factory=dict)
