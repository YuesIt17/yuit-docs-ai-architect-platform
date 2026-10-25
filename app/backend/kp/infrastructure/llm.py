"""LLM client: MOCK | OLLAMA | VLLM via OpenAI-compatible API with mutable runtime config.

Base URL allowlist prevents SSRF via PUT /v1/llm/config (SEC-04).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from kp.config import Settings

SUPPORTED_PROVIDERS = frozenset({"MOCK", "OLLAMA", "VLLM"})
MOCK_MODEL = "mock-graph-rag"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5:0.5b"
DEFAULT_VLLM_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_VLLM_MODEL = "Qwen/Qwen2.5-1.5B-Instruct-AWQ"


def _normalize_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def ollama_endpoint(settings: Settings) -> tuple[str, str]:
    """OLLAMA URL and model from Settings, with host-dev defaults instead of the MOCK model."""
    base_url = (settings.openai_base_url or "").strip() or DEFAULT_OLLAMA_BASE_URL
    model = (settings.llm_model or "").strip()
    if not model or model == MOCK_MODEL:
        model = DEFAULT_OLLAMA_MODEL
    return base_url, model


def vllm_endpoint(settings: Settings) -> tuple[str, str]:
    base_url = (settings.openai_base_url or "").strip() or DEFAULT_VLLM_BASE_URL
    model = (settings.llm_model or "").strip()
    if not model or model == MOCK_MODEL:
        model = DEFAULT_VLLM_MODEL
    return base_url, model


def provider_presets(settings: Settings) -> dict[str, dict[str, str]]:
    """UI presets: MOCK fixed; OLLAMA/VLLM from Settings."""
    o_url, o_model = ollama_endpoint(settings)
    v_url, v_model = vllm_endpoint(settings)
    return {
        "MOCK": {"base_url": "", "model": MOCK_MODEL},
        "OLLAMA": {"base_url": o_url, "model": o_model},
        "VLLM": {"base_url": v_url, "model": v_model},
    }


def allowed_llm_base_urls(settings: Settings) -> set[str]:
    raw = (settings.llm_allowed_base_urls or "").strip()
    urls = {_normalize_base_url(u) for u in raw.split(",") if u.strip()}
    # Always allow the configured settings URL when present.
    configured = _normalize_base_url(settings.openai_base_url or "")
    if configured:
        urls.add(configured)
    urls.update(
        {
            _normalize_base_url(DEFAULT_OLLAMA_BASE_URL),
            _normalize_base_url(DEFAULT_VLLM_BASE_URL),
        }
    )
    return {u for u in urls if u}


def validate_llm_base_url(settings: Settings, base_url: str) -> str:
    """Reject arbitrary external URLs (SSRF hardening for submission profile)."""
    normalized = _normalize_base_url(base_url)
    if not normalized:
        raise ValueError("base_url is required for non-MOCK providers")
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base_url scheme must be http or https")
    if parsed.username or parsed.password:
        raise ValueError("base_url must not include credentials")
    host = (parsed.hostname or "").lower()
    if host in {"169.254.169.254", "metadata.google.internal"}:
        raise ValueError("base_url host is not allowed")
    # Canonical form ends with /v1 for OpenAI-compatible clients.
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/v1"):
        normalized = f"{parsed.scheme}://{parsed.netloc}/v1"
    else:
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    allow = {_normalize_base_url(u) for u in allowed_llm_base_urls(settings)}
    if normalized not in allow:
        raise ValueError(
            f"base_url not in allowlist (set LLM_ALLOWED_BASE_URLS or use presets): {normalized}"
        )
    return normalized


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
            return self.runtime

        if provider == "VLLM":
            fallback_url, fallback_model = vllm_endpoint(self.settings)
        else:
            fallback_url, fallback_model = ollama_endpoint(self.settings)

        chosen_model = (model or "").strip()
        if not chosen_model or chosen_model == MOCK_MODEL:
            chosen_model = fallback_model

        requested = (base_url or "").strip()
        if requested:
            if not self.settings.llm_allow_runtime_url_override:
                # Only accept allowlisted URLs when override is disabled.
                chosen_url = validate_llm_base_url(self.settings, requested)
            else:
                chosen_url = validate_llm_base_url(self.settings, requested)
        else:
            chosen_url = validate_llm_base_url(self.settings, fallback_url)

        self.runtime = LLMRuntimeConfig(
            provider=provider,
            base_url=chosen_url,
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
            async with httpx.AsyncClient(timeout=5.0, trust_env=False, follow_redirects=False) as client:
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

            async with httpx.AsyncClient(
                trust_env=False, timeout=120.0, follow_redirects=False
            ) as http_async_client:
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
            usage_in = len(user.split())
            usage_out = len(text.split())
            meta = getattr(resp, "response_metadata", None) or {}
            token_usage = meta.get("token_usage") or meta.get("usage") or {}
            if isinstance(token_usage, dict):
                if token_usage.get("prompt_tokens") is not None:
                    usage_in = int(token_usage["prompt_tokens"])
                if token_usage.get("completion_tokens") is not None:
                    usage_out = int(token_usage["completion_tokens"])
            return text, usage_in, usage_out
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
        if provider == "VLLM":
            base_url, model = vllm_endpoint(settings)
        else:
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
