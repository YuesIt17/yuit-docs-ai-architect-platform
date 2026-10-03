"""LangGraph state machine: guard → route → retrieve/label → synthesize → output guard."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.security.guardrails import input_guard, output_guard
from app.security.rbac import Principal
from app.services.knowledge_store import KnowledgeStore
from app.services.llm import LLMClient


class KnowledgeAgent:
    def __init__(self, store: KnowledgeStore, llm: LLMClient):
        self.store = store
        self.llm = llm
        self.graph = self._build()

    def _build(self):
        g = StateGraph(AgentState)
        g.add_node("guard_input", self.guard_input)
        g.add_node("route", self.route)
        g.add_node("graph_retrieve", self.graph_retrieve)
        g.add_node("vector_retrieve", self.vector_retrieve)
        g.add_node("label_recognize", self.label_recognize_node)
        g.add_node("policy_check", self.policy_check)
        g.add_node("synthesize", self.synthesize)
        g.add_node("guard_output", self.guard_output_node)

        g.set_entry_point("guard_input")
        g.add_edge("guard_input", "route")
        g.add_conditional_edges(
            "route",
            self._after_route,
            {
                "chat": "graph_retrieve",
                "label": "label_recognize",
                "blocked": "guard_output",
            },
        )
        g.add_edge("graph_retrieve", "vector_retrieve")
        g.add_edge("vector_retrieve", "synthesize")
        g.add_edge("label_recognize", "policy_check")
        g.add_edge("policy_check", "synthesize")
        g.add_edge("synthesize", "guard_output")
        g.add_edge("guard_output", END)
        return g.compile()

    def _after_route(self, state: AgentState) -> str:
        if not state.get("guard_ok", False):
            return "blocked"
        return state.get("route", "chat")

    def guard_input(self, state: AgentState) -> dict[str, Any]:
        if state.get("modality") == "label":
            return {"guard_ok": True, "guarded_message": state.get("message", ""), "guard_reasons": []}
        result = input_guard(state.get("message", ""))
        if not result.ok:
            return {
                "guard_ok": False,
                "guarded_message": result.text,
                "guard_reasons": result.reasons,
                "answer": "Запрос заблокирован Input Guard (подозрение на prompt injection).",
                "acl_decision": "deny_input",
                "citations": [],
            }
        return {"guard_ok": True, "guarded_message": result.text, "guard_reasons": []}

    def route(self, state: AgentState) -> dict[str, Any]:
        if state.get("modality") == "label":
            return {"route": "label"}
        msg = (state.get("guarded_message") or "").lower()
        if any(k in msg for k in ("этикет", "label", "ocr", "упаков")):
            return {"route": "label"}
        return {"route": "chat"}

    def graph_retrieve(self, state: AgentState) -> dict[str, Any]:
        principal = Principal(user_id=state["user_id"], role=state["role"])
        doc_ids = self.store.graph_resolve_doc_ids(state.get("guarded_message", ""))
        return {"retrieved": [{"via": "graph", "doc_ids": doc_ids}]}

    def vector_retrieve(self, state: AgentState) -> dict[str, Any]:
        principal = Principal(user_id=state["user_id"], role=state["role"])
        hits = self.store.hybrid_retrieve(state.get("guarded_message", ""), principal, top_k=5)
        retrieved = []
        citations = []
        for h in hits:
            retrieved.append(
                {
                    "chunk_id": h.chunk.chunk_id,
                    "doc_id": h.document.doc_id,
                    "text": h.chunk.text,
                    "corpus": h.document.corpus,
                    "classification": h.document.classification,
                    "score": h.score,
                    "via": h.via,
                    "title": h.document.title,
                }
            )
            citations.append(
                {
                    "doc_id": h.document.doc_id,
                    "chunk_id": h.chunk.chunk_id,
                    "corpus": h.document.corpus,
                    "classification": h.document.classification,
                    "snippet": h.chunk.text[:240],
                    "score": h.score,
                }
            )
        return {"retrieved": retrieved, "citations": citations, "acl_decision": "allow"}

    def label_recognize_node(self, state: AgentState) -> dict[str, Any]:
        # Label extract is injected by API before invoke; this node enriches query
        extract = state.get("label_extract") or {}
        allergens = ", ".join(extract.get("allergens") or [])
        msg = f"Label allergens: {allergens}. Ingredients: {extract.get('ingredients')}. Brand: {extract.get('brand')}"
        return {"guarded_message": msg, "route": "label"}

    def policy_check(self, state: AgentState) -> dict[str, Any]:
        principal = Principal(user_id=state["user_id"], role=state["role"])
        query = state.get("guarded_message", "")
        hits = self.store.hybrid_retrieve(query + " allergen policy", principal, top_k=5)
        citations = []
        retrieved = []
        for h in hits:
            item = {
                "chunk_id": h.chunk.chunk_id,
                "doc_id": h.document.doc_id,
                "text": h.chunk.text,
                "corpus": h.document.corpus,
                "classification": h.document.classification,
                "score": h.score,
                "via": "policy",
                "title": h.document.title,
            }
            retrieved.append(item)
            citations.append(
                {
                    "doc_id": h.document.doc_id,
                    "chunk_id": h.chunk.chunk_id,
                    "corpus": h.document.corpus,
                    "classification": h.document.classification,
                    "snippet": h.chunk.text[:240],
                    "score": h.score,
                }
            )
        return {"retrieved": retrieved, "citations": citations}

    async def synthesize(self, state: AgentState) -> dict[str, Any]:
        if state.get("acl_decision") == "deny_input" and state.get("answer"):
            return {"tokens_in": 0, "tokens_out": 0, "model_uri": self.llm.model_uri}
        ctx_lines = []
        for item in state.get("retrieved") or []:
            if "text" in item:
                ctx_lines.append(f"[{item.get('doc_id')}|{item.get('classification')}] {item['text']}")
        if state.get("modality") == "label" or state.get("route") == "label":
            user = (
                f"LABEL_EXTRACT: {state.get('label_extract')}\n"
                f"CONTEXT:\n" + "\n".join(ctx_lines[:6])
            )
            system = (
                "You are RetailPartnerX Policy Analyst. Explain label findings vs store policies. "
                "Use only CONTEXT. Reply in Russian."
            )
        else:
            user = f"QUESTION: {state.get('guarded_message')}\nCONTEXT:\n" + "\n".join(ctx_lines[:8])
            system = (
                "You are RetailPartnerX Knowledge Assistant. Answer using CONTEXT only. "
                "Cite doc ids. Reply in Russian. If context empty, say insufficient access/data."
            )
        if not ctx_lines:
            return {
                "answer": "Недостаточно релевантного контекста в документах, доступных вашей роли.",
                "degraded": False,
                "tokens_in": 0,
                "tokens_out": 0,
                "model_uri": self.llm.model_uri,
            }
        answer, tin, tout = await self.llm.complete(system, user)
        degraded = answer.startswith("[degraded:")
        return {
            "answer": answer,
            "degraded": degraded,
            "tokens_in": tin,
            "tokens_out": tout,
            "model_uri": self.llm.model_uri,
        }

    def guard_output_node(self, state: AgentState) -> dict[str, Any]:
        if state.get("acl_decision") == "deny_input":
            return {}
        classifications = [c.get("classification", "public") for c in state.get("citations") or []]
        result = output_guard(
            state.get("answer", ""),
            state.get("citations") or [],
            state.get("role", "guest"),
            classifications,
        )
        if not result.ok:
            return {"answer": result.text, "acl_decision": "deny_output", "citations": []}
        return {"answer": result.text, "acl_decision": state.get("acl_decision", "allow")}

    async def arun(self, state: AgentState) -> AgentState:
        return await self.graph.ainvoke(state)
