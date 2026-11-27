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


class FlagdUnavailable(Exception):
    """OFREP could not be evaluated. Callers fail closed for security flags."""


@dataclass(frozen=True)
class FlagEvaluation:
    kill_switch: bool = False
    agent_enabled: bool = True
    prompt_version: str = "v1"
    model_route: str = "chat-default"
    # in_memory | flagd | flagd_unavailable | disabled
    provider_status: str = "in_memory"
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

    def _ofrep_value(self, key: str, context: dict[str, Any]) -> Any:
        """Read one flag from Flagd. Raises FlagdUnavailable; does not fall open."""
        base = (self.settings.flagd_url or "").rstrip("/")
        url = f"{base}/ofrep/v1/evaluate/{key}"
        try:
            with httpx.Client(timeout=2.0, trust_env=False) as client:
                resp = client.post(url, json={"context": context})
        except Exception as exc:
            raise FlagdUnavailable(key) from exc
        if resp.status_code >= 400:
            raise FlagdUnavailable(key)
        try:
            data = resp.json()
        except Exception as exc:
            raise FlagdUnavailable(key) from exc
        if isinstance(data, dict) and "value" in data:
            return data["value"]
        variant = data.get("variant") if isinstance(data, dict) else None
        flag = self._defs.get(key) or {}
        variants = flag.get("variants") or {}
        if variant in variants:
            return variants[variant]
        raise FlagdUnavailable(key)

    def _fail_closed(self) -> FlagEvaluation:
        """Security flags deny new runs. Prompt and model stay on the file defaults."""
        return FlagEvaluation(
            kill_switch=True,
            agent_enabled=False,
            prompt_version=str(
                self._default_variant_value(FLAG_PROMPT_VERSION, self.settings.prompt_version)
            ),
            model_route=str(
                self._default_variant_value(
                    FLAG_MODEL_ROUTE,
                    self.settings.litellm_model_alias or "chat-default",
                )
            ),
            provider_status="flagd_unavailable",
        )

    def _from_defaults(self) -> FlagEvaluation:
        return FlagEvaluation(
            kill_switch=bool(self._default_variant_value(FLAG_KILL_SWITCH, False)),
            agent_enabled=bool(self._default_variant_value(FLAG_AGENT_ENABLED, True)),
            prompt_version=str(
                self._default_variant_value(FLAG_PROMPT_VERSION, self.settings.prompt_version)
            ),
            model_route=str(
                self._default_variant_value(
                    FLAG_MODEL_ROUTE,
                    self.settings.litellm_model_alias or "chat-default",
                )
            ),
            provider_status="in_memory",
        )

    def evaluate(self, *, agent_id: str, role: str = "", user_id: str = "") -> FlagEvaluation:
        if not self.settings.feature_flags_enabled:
            return FlagEvaluation(
                prompt_version=self.settings.prompt_version,
                provider_status="disabled",
            )

        # In-process overrides are a test hook and replace OFREP for the whole evaluation.
        if self._overrides or not self.settings.flagd_url:
            return self._from_defaults()

        context = {
            "targetingKey": user_id or role or agent_id,
            "agent_id": agent_id,
            "role": role,
            "user_id": user_id,
        }
        try:
            kill_switch = bool(self._ofrep_value(FLAG_KILL_SWITCH, context))
            agent_enabled = bool(self._ofrep_value(FLAG_AGENT_ENABLED, context))
            prompt_version = str(self._ofrep_value(FLAG_PROMPT_VERSION, context))
            model_route = str(self._ofrep_value(FLAG_MODEL_ROUTE, context))
        except FlagdUnavailable:
            return self._fail_closed()
        return FlagEvaluation(
            kill_switch=kill_switch,
            agent_enabled=agent_enabled,
            prompt_version=prompt_version,
            model_route=model_route,
            provider_status="flagd",
        )
