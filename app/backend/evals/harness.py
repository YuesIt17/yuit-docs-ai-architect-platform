"""Run the golden set through the real agent and score retrieval and access control."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOLDEN_PATH = Path(__file__).with_name("golden.jsonl")
REFUSAL_PREFIX = "insufficient relevant context"


@dataclass
class GoldenCase:
    id: str
    role: str
    question: str
    ground_truth: str = ""
    expected_doc_ids: list[str] = field(default_factory=list)
    forbidden_doc_ids: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    expect_refusal: bool = False


@dataclass
class CaseResult:
    case: GoldenCase
    answer: str
    contexts: list[str]
    cited_doc_ids: list[str]
    acl_decision: str
    leaks: list[str]
    refused: bool
    degraded: bool

    @property
    def recall(self) -> float | None:
        if not self.case.expected_doc_ids:
            return None
        found = set(self.case.expected_doc_ids) & set(self.cited_doc_ids)
        return len(found) / len(self.case.expected_doc_ids)


def load_golden(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenCase(**json.loads(line)) for line in lines if line.strip()]


def score_state(case: GoldenCase, state: dict[str, Any]) -> CaseResult:
    answer = state.get("answer") or ""
    citations = state.get("citations") or []
    cited = [str(c["doc_id"]) for c in citations if c.get("doc_id")]
    contexts = [str(r["text"]) for r in state.get("retrieved") or [] if r.get("text")]
    # Retrieved context counts too: a forbidden chunk that reaches the LLM is a leak even if uncited.
    retrieved = {str(r["doc_id"]) for r in state.get("retrieved") or [] if r.get("doc_id")}
    leaks = [f"doc:{d}" for d in case.forbidden_doc_ids if d in set(cited) | retrieved]
    leaks += [f"term:{t}" for t in case.forbidden_terms if t.lower() in answer.lower()]
    return CaseResult(
        case=case,
        answer=answer,
        contexts=contexts,
        cited_doc_ids=cited,
        acl_decision=str(state.get("acl_decision") or ""),
        leaks=leaks,
        refused=answer.strip().lower().startswith(REFUSAL_PREFIX),
        degraded=bool(state.get("degraded")),
    )


async def run_case(agent, case: GoldenCase) -> CaseResult:
    state = await agent.arun(
        {
            "request_id": f"eval-{case.id}",
            "message": case.question,
            "modality": "chat",
            "role": case.role,
            "user_id": f"eval-{case.role}",
            "errors": [],
        }
    )
    return score_state(case, state)


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    recalls = [r.recall for r in results if r.recall is not None]
    # Reported but not gated: a golden case lists the required sources, not every acceptable one.
    precisions = [
        len(set(r.case.expected_doc_ids) & set(r.cited_doc_ids)) / len(set(r.cited_doc_ids))
        for r in results
        if r.case.expected_doc_ids and r.cited_doc_ids
    ]
    refusal_cases = [r for r in results if r.case.expect_refusal]
    return {
        "cases": len(results),
        "acl_leaks": sum(len(r.leaks) for r in results),
        "retrieval_recall": sum(recalls) / len(recalls) if recalls else None,
        "citation_precision": sum(precisions) / len(precisions) if precisions else None,
        "refusal_accuracy": (
            sum(r.refused for r in refusal_cases) / len(refusal_cases) if refusal_cases else None
        ),
        "degraded_answers": sum(r.degraded for r in results),
    }


def check_deterministic(summary: dict[str, Any], limits: dict[str, float]) -> list[str]:
    """Return one message per breached threshold."""
    failures = []
    if summary["acl_leaks"] > limits["acl_leaks_max"]:
        failures.append(f"acl_leaks {summary['acl_leaks']} > {limits['acl_leaks_max']}")
    if summary["refusal_accuracy"] is not None and summary["refusal_accuracy"] < limits["refusal_accuracy_min"]:
        failures.append(f"refusal_accuracy {summary['refusal_accuracy']:.2f} < {limits['refusal_accuracy_min']}")
    if summary["retrieval_recall"] is not None and summary["retrieval_recall"] < limits["retrieval_recall_min"]:
        failures.append(f"retrieval_recall {summary['retrieval_recall']:.2f} < {limits['retrieval_recall_min']}")
    return failures
