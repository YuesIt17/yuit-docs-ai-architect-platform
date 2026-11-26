"""Feature flags: in-memory (CI) or Flagd OFREP (desktop). OpenFeature-shaped API (ADR-013)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from kp.config import Settings

FLAG_KILL_SWITCH = "kill_switch_agents"
FLAG_AGENT_ENABLED = "agent_enabled"
FLAG_PROMPT_VERSION = "prompt_version"
FLAG_MODEL_ROUTE = "model_route"


def default_flags_path() -> Path:
    """`app/infra/flagd/flags.json` next to the backend tree."""
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root.parent / "infra" / "flagd" / "flags.json"


def resolve_flags_path(settings: Settings) -> Path:
    raw = (settings.feature_flags_file or "").strip()
    if raw:
        return Path(raw)
    return default_flags_path()


@dataclass(frozen=True)
class FlagEvaluation:
    kill_switch: bool = False
    agent_enabled: bool = True
    prompt_version: str = "v1"
    model_route: str = "chat-default"
    variants: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.variants is None:
            object.__setattr__(
                self,
                "variants",
                {
                    FLAG_KILL_SWITCH: "on" if self.kill_switch else "off",
                    FLAG_AGENT_ENABLED: "on" if self.agent_enabled else "off",
                    FLAG_PROMPT_VERSION: self.prompt_version,
                    FLAG_MODEL_ROUTE: self.model_route,
                },
            )


class FeatureFlagService:
    """Evaluate rollout flags for an agent turn."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._defs = self._load_defs(resolve_flags_path(settings))
        self._overrides: dict[str, Any] = {}

    @staticmethod
    def _load_defs(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        flags = raw.get("flags") if isinstance(raw, dict) else None
        return flags if isinstance(flags, dict) else {}

    def override(self, key: str, value: Any) -> None:
        """Test helper: force a flag value in the in-memory path."""
        self._overrides[key] = value

    def clear_overrides(self) -> None:
        self._overrides.clear()

    def _default_variant_value(self, key: str, fallback: Any) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        flag = self._defs.get(key) or {}
        variants = flag.get("variants") or {}
        default_name = flag.get("defaultVariant")
        if default_name in variants:
            return variants[default_name]
        return fallback

    def _ofrep_evaluate(self, key: str, default: Any, context: dict[str, Any]) -> Any:
        base = (self.settings.flagd_url or "").rstrip("/")
        url = f"{base}/ofrep/v1/evaluate/{key}"
        try:
            with httpx.Client(timeout=2.0, trust_env=False) as client:
                resp = client.post(url, json={"context": context})
            if resp.status_code >= 400:
                return self._default_variant_value(key, default)
            data = resp.json()
            if "value" in data:
                return data["value"]
            variant = data.get("variant")
            flag = self._defs.get(key) or {}
            variants = flag.get("variants") or {}
            if variant in variants:
                return variants[variant]
        except Exception:
            return self._default_variant_value(key, default)
        return self._default_variant_value(key, default)

    def _value(self, key: str, default: Any, context: dict[str, Any]) -> Any:
        if key in self._overrides or not self.settings.flagd_url:
            return self._default_variant_value(key, default)
        return self._ofrep_evaluate(key, default, context)

    def evaluate(self, *, agent_id: str, role: str = "", user_id: str = "") -> FlagEvaluation:
        if not self.settings.feature_flags_enabled:
            return FlagEvaluation(prompt_version=self.settings.prompt_version)

        context = {
            "targetingKey": user_id or role or agent_id,
            "agent_id": agent_id,
            "role": role,
            "user_id": user_id,
        }
        return FlagEvaluation(
            kill_switch=bool(self._value(FLAG_KILL_SWITCH, False, context)),
            agent_enabled=bool(self._value(FLAG_AGENT_ENABLED, True, context)),
            prompt_version=str(
                self._value(FLAG_PROMPT_VERSION, self.settings.prompt_version, context)
            ),
            model_route=str(
                self._value(
                    FLAG_MODEL_ROUTE,
                    self.settings.litellm_model_alias or "chat-default",
                    context,
                )
            ),
        )
