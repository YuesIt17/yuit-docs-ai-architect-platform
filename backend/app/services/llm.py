"""LLM client: MOCK | VLLM | OLLAMA via OpenAI-compatible API with mutable runtime config."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "MOCK": {"base_url": "", "model": "mock-graph-rag"},
    "OLLAMA": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:0.5b"},
    "VLLM": {"base_url": "http://localhost:8000/v1", "model": "Qwen/Qwen2.5-7B-Instruct"},
}


@dataclass
class LLMRuntimeConfig:
    provider: str = "MOCK"
    base_url: str = ""
    model: str = "mock-graph-rag"
    api_key: str = "not-needed"

    @classmethod
    def from_settings(cls, settings: Settings) -> LLMRuntimeConfig:
        provider = settings.llm_provider.upper()
        preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["MOCK"])
        base = settings.openai_base_url or preset["base_url"]
        model = settings.llm_model or preset["model"]
        return cls(provider=provider, base_url=base, model=model, api_key=settings.openai_api_key)

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

    def apply_config(self, provider: str, base_url: str | None = None, model: str | None = None) -> LLMRuntimeConfig:
        provider = provider.upper()
        if provider not in PROVIDER_PRESETS:
            raise ValueError(f"unsupported provider: {provider}")
        preset = PROVIDER_PRESETS[provider]
        self.runtime = LLMRuntimeConfig(
            provider=provider,
            base_url=(base_url if base_url is not None else preset["base_url"]),
            model=(model if model is not None else preset["model"]),
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
            # allow passing host without /v1
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
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            base = self.runtime.base_url
            if provider == "OLLAMA" and base and "11434" not in base and "ollama" not in base:
                base = "http://localhost:11434/v1"
            llm = ChatOpenAI(
                model=self.runtime.model,
                api_key=self.runtime.api_key or "not-needed",
                base_url=base,
                temperature=0.1,
                max_tokens=max_tokens,
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
