"""LLM client: MOCK | OLLAMA via OpenAI-compatible API with mutable runtime config.

Ollama base URL and model come from Settings (Helm `llm.*` → env / .env), not from
hardcoded presets in this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from kp.config import Settings

SUPPORTED_PROVIDERS = frozenset({"MOCK", "OLLAMA"})
MOCK_MODEL = "mock-graph-rag"
# Used only when Settings still carry the MOCK defaults (empty URL / mock model name).
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5:0.5b"


def ollama_endpoint(settings: Settings) -> tuple[str, str]:
    """OLLAMA URL and model from Settings, with host-dev defaults instead of the MOCK model."""
    base_url = (settings.openai_base_url or "").strip() or DEFAULT_OLLAMA_BASE_URL
    model = (settings.llm_model or "").strip()
    if not model or model == MOCK_MODEL:
        model = DEFAULT_OLLAMA_MODEL
    return base_url, model


def provider_presets(settings: Settings) -> dict[str, dict[str, str]]:
    """UI presets: MOCK is fixed; OLLAMA URL/model come from Helm / .env via Settings."""
    base_url, model = ollama_endpoint(settings)
    return {
        "MOCK": {"base_url": "", "model": MOCK_MODEL},
        "OLLAMA": {"base_url": base_url, "model": model},
    }


@dataclass
class LLMRuntimeConfig:
    provider: str = "MOCK"
    base_url: str = ""
    model: str = MOCK_MODEL
    api_key: str = "not-needed"

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMRuntimeConfig:
        provider = settings.llm_provider.upper()
        if provider not in SUPPORTED_PROVIDERS:
            provider = "MOCK"
        if provider == "MOCK":
            return cls(
                provider=provider,
                base_url="",
                model=MOCK_MODEL,
                api_key=settings.openai_api_key,
            )
        base_url, model = ollama_endpoint(settings)
        return cls(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=settings.openai_api_key,
        )

    @property
    def model_uri(self) -> str:
        return f"{self.provider.lower()}://{self.model}"


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.runtime = LLMRuntimeConfig.from_settings(settings)

    @property
    def model_uri(self) -> str:
        return self.runtime.model_uri

    def get_config(self) -> LLMRuntimeConfig:
        return self.runtime

    def apply_config(
        self, provider: str, base_url: str | None = None, model: str | None = None
    ) -> LLMRuntimeConfig:
        provider = provider.upper()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported provider: {provider}")
        if provider == "MOCK":
            self.runtime = LLMRuntimeConfig(
                provider=provider,
                base_url="",
                model=MOCK_MODEL,
                api_key=self.settings.openai_api_key,
            )
        else:
            # Prefer an explicit URL/model; otherwise Settings, not the MOCK model name.
            fallback_url, fallback_model = ollama_endpoint(self.settings)
            chosen_model = (model or "").strip()
            if not chosen_model or chosen_model == MOCK_MODEL:
                chosen_model = fallback_model
            self.runtime = LLMRuntimeConfig(
                provider=provider,
                base_url=(base_url or "").strip() or fallback_url,
                model=chosen_model,
                api_key=self.settings.openai_api_key,
            )
        return self.runtime

    async def probe(self) -> dict:
        cfg = self.runtime
        if cfg.provider == "MOCK":
            return {
                "provider": cfg.provider,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "reachable": True,
                "detail": "mock provider always reachable",
                "model_uri": cfg.model_uri,
            }
        url = cfg.base_url.rstrip("/")
        if not url.endswith("/v1"):
            probe_url = f"{url}/v1/models" if not url.endswith("/models") else url
        else:
            probe_url = f"{url}/models"
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                resp = await client.get(
                    probe_url,
                    headers={"Authorization": f"Bearer {cfg.api_key}"},
                )
            ok = resp.status_code < 500
            detail = f"HTTP {resp.status_code}"
            if ok and resp.status_code == 200:
                try:
                    data = resp.json()
                    ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                    if ids:
                        detail = f"models: {', '.join(ids[:5])}"
                except Exception:
                    pass
            return {
                "provider": cfg.provider,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "reachable": ok,
                "detail": detail,
                "model_uri": cfg.model_uri,
            }
        except Exception as exc:
            return {
                "provider": cfg.provider,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "reachable": False,
                "detail": f"{exc.__class__.__name__}: {exc}",
                "model_uri": cfg.model_uri,
            }

    async def complete(self, system: str, user: str, max_tokens: int = 512) -> tuple[str, int, int]:
        provider = self.runtime.provider.upper()
        if provider == "MOCK":
            return self._mock_complete(system, user), len(user.split()), 80
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI

            # trust_env=False: a system/HTTP proxy must not intercept 127.0.0.1 Ollama (502).
            async with httpx.AsyncClient(trust_env=False, timeout=120.0) as http_async_client:
                llm = ChatOpenAI(
                    model=self.runtime.model,
                    api_key=self.runtime.api_key or "not-needed",
                    base_url=self.runtime.base_url,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    http_async_client=http_async_client,
                )
                resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            return text, len(user.split()), len(text.split())
        except Exception as exc:
            answer = self._mock_complete(system, user)
            return f"[degraded:{exc.__class__.__name__}] {answer}", len(user.split()), 40

    def _mock_complete(self, system: str, user: str) -> str:
        if "CONTEXT:" in user:
            ctx = user.split("CONTEXT:", 1)[1].strip()
            lines = [ln.strip() for ln in ctx.splitlines() if ln.strip()][:4]
            joined = " ".join(lines)[:800]
            return (
                "На основе корпоративной базы знаний RetailPartnerX: "
                f"{joined} "
                "Ответ сформирован GraphRAG с цитированием источников."
            )
        if "LABEL_EXTRACT:" in user:
            return (
                "По этикетке извлечены атрибуты. Проверьте аллергены относительно Policy KB. "
                "Рекомендуется сверить состав с карточкой SKU в PIM."
            )
        return "Недостаточно релевантного контекста в доступных вам документах RetailPartnerX."
