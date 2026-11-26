"""In-process agent registry: load YAML manifests, register, resolve runtime bindings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from kp.agents.manifest import AgentManifest, ResolvedAgent
from kp.config import Settings
from kp.infrastructure.llm import LLMClient
from kp.infrastructure.session_memory import uses_postgres


class AgentRegistryError(Exception):
    """Base registry error."""


class AgentNotFoundError(AgentRegistryError):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"agent not found: {agent_id}")


class AgentDisabledError(AgentRegistryError):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"agent disabled: {agent_id}")


class AgentRoleDeniedError(AgentRegistryError):
    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role
        super().__init__(f"role {role!r} cannot invoke agent {agent_id}")


class AgentKillSwitchError(AgentRegistryError):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"agent kill-switch active: {agent_id}")


class AgentConflictError(AgentRegistryError):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"agent already registered: {agent_id}")


class AgentManifestInvalidError(AgentRegistryError):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


def default_manifests_dir() -> Path:
    """`<backend>/agents` — next to `kp/`, not inside the package."""
    return Path(__file__).resolve().parents[2] / "agents"


def resolve_manifests_dir(settings: Settings) -> Path:
    raw = (settings.agent_manifests_dir or "").strip()
    return Path(raw) if raw else default_manifests_dir()


class AgentRegistry:
    """Loads declarative Agent manifests and binds them to live settings."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentManifest] = {}
        self._sources: dict[str, Literal["disk", "api"]] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> AgentRegistry:
        registry = cls()
        registry.load_dir(resolve_manifests_dir(settings))
        return registry

    def load_dir(self, directory: Path) -> int:
        """Load `*.yaml` / `*.yml` from directory. Missing directory is a no-op."""
        if not directory.is_dir():
            return 0
        loaded = 0
        for path in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            self.load_file(path, source="disk", overwrite=True)
            loaded += 1
        return loaded

    def load_file(
        self,
        path: Path,
        *,
        source: Literal["disk", "api"] = "disk",
        overwrite: bool = True,
    ) -> AgentManifest:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AgentManifestInvalidError(f"cannot read {path}: {exc}") from exc
        except yaml.YAMLError as exc:
            raise AgentManifestInvalidError(f"invalid YAML in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise AgentManifestInvalidError(f"{path} must contain a mapping document")
        try:
            manifest = AgentManifest.model_validate(raw)
        except ValidationError as exc:
            raise AgentManifestInvalidError(f"{path}: {exc}") from exc
        return self.register(manifest, source=source, overwrite=overwrite)

    def register(
        self,
        manifest: AgentManifest,
        *,
        source: Literal["disk", "api"] = "api",
        overwrite: bool = False,
    ) -> AgentManifest:
        agent_id = manifest.metadata.id
        if agent_id in self._agents and not overwrite:
            raise AgentConflictError(agent_id)
        self._agents[agent_id] = manifest
        self._sources[agent_id] = source
        return manifest

    def list(self) -> list[AgentManifest]:
        return [self._agents[key] for key in sorted(self._agents)]

    def get(self, agent_id: str) -> AgentManifest | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> AgentManifest:
        manifest = self.get(agent_id)
        if manifest is None:
            raise AgentNotFoundError(agent_id)
        return manifest

    def authorize(self, agent_id: str, role: str) -> AgentManifest:
        """Return the manifest if enabled and the role may invoke it."""
        manifest = self.require(agent_id)
        if not manifest.spec.enabled:
            raise AgentDisabledError(agent_id)
        allowed = set(manifest.spec.security.required_roles)
        if role not in allowed:
            raise AgentRoleDeniedError(agent_id, role)
        return manifest

    def resolve(self, agent_id: str, settings: Settings, llm: LLMClient) -> ResolvedAgent:
        manifest = self.require(agent_id)
        cfg = llm.get_config()
        memory = manifest.spec.memory
        if memory.backend == "settings":
            effective_memory = "postgres" if uses_postgres(settings) else "memory"
        else:
            effective_memory = memory.backend
        api_paths = [
            t.path
            for t in manifest.spec.triggers
            if t.type == "api" and t.enabled and t.path
        ]
        return ResolvedAgent(
            manifest=manifest,
            effective_model_provider=cfg.provider,
            effective_model=cfg.model,
            effective_model_uri=cfg.model_uri,
            effective_prompt_version=settings.prompt_version,
            effective_memory_backend=effective_memory,
            tool_ids=[t.id for t in manifest.spec.tools],
            api_trigger_paths=api_paths,
            source=self._sources.get(agent_id, "disk"),
            extras={
                "runtime": manifest.spec.runtime,
                "entrypoint": manifest.spec.entrypoint,
                "index_version": settings.index_version,
                "policy_version": settings.policy_version,
            },
        )
