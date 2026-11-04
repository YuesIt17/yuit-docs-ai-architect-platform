"""LLM-as-a-Judge scoring with DeepEval, using only a local OpenAI-compatible model.

Requires the optional dependency: pip install -e ".[eval]"
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx

# Eval data must stay inside the perimeter, so DeepEval telemetry is turned off before it loads.
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("ERROR_REPORTING", "NO")

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "vllm", "ollama"}


def require_local_url(base_url: str) -> str:
    """Refuse any judge endpoint outside the closed perimeter (ADR-001)."""
    host = urlparse(base_url).hostname
    if host not in LOCAL_HOSTS:
        raise ValueError(f"Judge base URL must be local, got host {host!r}. Allowed: {sorted(LOCAL_HOSTS)}")
    return base_url.rstrip("/")


def complete(base_url: str, model: str, prompt: str, *, transport: httpx.BaseTransport | None = None) -> str:
    """Call /chat/completions with a JSON-only response, which judge prompts parse."""
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    with httpx.Client(timeout=300.0, trust_env=False, transport=transport) as client:
        response = client.post(f"{base_url}/chat/completions", json=body)
        response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def build_judge(base_url: str, model: str):
    from deepeval.models import DeepEvalBaseLLM

    url = require_local_url(base_url)

    class LocalJudge(DeepEvalBaseLLM):
        def load_model(self):
            return model

        def generate(self, prompt: str, schema: Any = None) -> Any:
            text = complete(url, model, prompt)
            return schema.model_validate_json(text) if schema is not None else text

        async def a_generate(self, prompt: str, schema: Any = None) -> Any:
            return self.generate(prompt, schema)

        def get_model_name(self) -> str:
            return f"local:{model}"

    return LocalJudge()


def score_results(results: list, judge) -> dict[str, Any]:
    """Score answerable cases. Refusal and ACL cases have no ground truth and are not judged."""
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        FaithfulnessMetric,
    )
    from deepeval.test_case import LLMTestCase

    factories = {
        "faithfulness": FaithfulnessMetric,
        "answer_relevancy": AnswerRelevancyMetric,
        "contextual_precision": ContextualPrecisionMetric,
        "contextual_recall": ContextualRecallMetric,
    }
    scores: dict[str, list[float]] = {name: [] for name in factories}
    errors: list[str] = []
    per_case: dict[str, dict[str, float]] = {}
    for result in results:
        if not result.case.ground_truth or not result.contexts:
            continue
        test_case = LLMTestCase(
            input=result.case.question,
            actual_output=result.answer,
            expected_output=result.case.ground_truth,
            retrieval_context=result.contexts,
        )
        per_case[result.case.id] = {}
        for name, factory in factories.items():
            metric = factory(model=judge, async_mode=False, include_reason=False)
            try:
                metric.measure(test_case)
            except Exception as exc:  # A small model can return malformed JSON; report it, do not hide it.
                errors.append(f"{result.case.id}/{name}: {exc.__class__.__name__}")
                continue
            scores[name].append(float(metric.score))
            per_case[result.case.id][name] = float(metric.score)
    means = {name: (sum(v) / len(v) if v else None) for name, v in scores.items()}
    return {"means": means, "per_case": per_case, "errors": errors}


def check_judge(means: dict[str, float | None], limits: dict[str, float]) -> list[str]:
    """A metric with no scores is a failure: an unscored run must not pass the gate."""
    failures = []
    for name, value in means.items():
        limit = limits[f"{name}_min"]
        if value is None:
            failures.append(f"{name} produced no scores")
        elif value < limit:
            failures.append(f"{name} {value:.2f} < {limit}")
    return failures
