"""LLM client: MOCK | VLLM | OLLAMA via OpenAI-compatible API."""

from __future__ import annotations

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_uri = f"{settings.llm_provider.lower()}://{settings.llm_model}"

    async def complete(self, system: str, user: str, max_tokens: int = 512) -> tuple[str, int, int]:
        provider = self.settings.llm_provider.upper()
        if provider == "MOCK":
            return self._mock_complete(system, user), len(user.split()), 80
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage

            base = self.settings.openai_base_url
            if provider == "OLLAMA" and "11434" not in base:
                base = "http://localhost:11434/v1"
            llm = ChatOpenAI(
                model=self.settings.llm_model,
                api_key=self.settings.openai_api_key,
                base_url=base,
                temperature=0.1,
                max_tokens=max_tokens,
            )
            resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
            text = resp.content if isinstance(resp.content, str) else str(resp.content)
            return text, len(user.split()), len(text.split())
        except Exception as exc:
            # Soft degrade
            answer, tin, tout = self._mock_complete(system, user), len(user.split()), 40
            return f"[degraded:{exc.__class__.__name__}] {answer}", tin, tout

    def _mock_complete(self, system: str, user: str) -> str:
        # Extract context block if present
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
