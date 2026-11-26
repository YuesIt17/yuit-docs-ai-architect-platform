"""Declarative agent manifests and in-process registry."""

from __future__ import annotations

from kp.agents.manifest import AgentManifest, ResolvedAgent
from kp.agents.registry import AgentRegistry, default_manifests_dir

__all__ = [
    "AgentManifest",
    "AgentRegistry",
    "ResolvedAgent",
    "default_manifests_dir",
]
