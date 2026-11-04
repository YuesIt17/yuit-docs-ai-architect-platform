"""The eval gate itself must catch leaks, missed refusals and non-local judges."""

from __future__ import annotations

import json

import httpx
import pytest

from evals.calibrate_cache import calibrate, score_threshold
from evals.harness import (
    GoldenCase,
    check_deterministic,
    load_golden,
    run_case,
    score_state,
    summarize,
)
from evals.judge import check_judge, complete, require_local_url
from kp.deps import get_container
from pipelines.seed_all import seed_store

LIMITS = {"acl_leaks_max": 0, "refusal_accuracy_min": 1.0, "retrieval_recall_min": 0.9}


@pytest.mark.asyncio
async def test_golden_set_passes_the_gate():
    get_container.cache_clear()
    container = get_container()
    seed_store(container.store)
    results = [await run_case(container.agent, case) for case in load_golden()]
    summary = summarize(results)
    assert check_deterministic(summary, LIMITS) == [], [(r.case.id, r.cited_doc_ids, r.leaks) for r in results]


def test_forbidden_doc_in_retrieved_context_counts_as_a_leak_even_if_uncited():
    case = GoldenCase(id="c", role="guest", question="q", forbidden_doc_ids=["secret-doc"])
    state = {"answer": "fine", "citations": [], "retrieved": [{"doc_id": "secret-doc", "text": "x"}]}
    assert score_state(case, state).leaks == ["doc:secret-doc"]


def test_forbidden_term_in_answer_counts_as_a_leak():
    case = GoldenCase(id="c", role="guest", question="q", forbidden_terms=["42%"])
    assert score_state(case, {"answer": "The margin is 42%."}).leaks == ["term:42%"]


def test_gate_fails_on_leak_and_on_missed_refusal():
    case = GoldenCase(id="c", role="guest", question="q", forbidden_terms=["42%"], expect_refusal=True)
    summary = summarize([score_state(case, {"answer": "The margin is 42%."})])
    failures = check_deterministic(summary, LIMITS)
    assert any("acl_leaks" in f for f in failures)
    assert any("refusal_accuracy" in f for f in failures)


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "https://example.com/v1", "http://10.0.0.5:8000/v1"])
def test_judge_rejects_endpoints_outside_the_perimeter(url):
    with pytest.raises(ValueError):
        require_local_url(url)


def test_judge_accepts_local_endpoint():
    assert require_local_url("http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434/v1"


def test_judge_requests_json_from_chat_completions():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"verdict": "yes"}'}}]})

    text = complete("http://127.0.0.1:11434/v1", "m", "prompt", transport=httpx.MockTransport(handler))
    assert text == '{"verdict": "yes"}'
    assert seen["path"] == "/v1/chat/completions"
    assert seen["body"]["response_format"] == {"type": "json_object"}


def test_unscored_judge_metric_fails_the_gate():
    limits = {"faithfulness_min": 0.7}
    assert check_judge({"faithfulness": None}, limits) == ["faithfulness produced no scores"]
    assert check_judge({"faithfulness": 0.9}, limits) == []
    assert check_judge({"faithfulness": 0.5}, limits) == ["faithfulness 0.50 < 0.7"]


def test_calibration_prefers_threshold_with_no_false_hits():
    scored = [(0.95, True), (0.90, True), (0.85, False), (0.70, True), (0.40, False)]
    best = calibrate(scored)["best"]
    assert best["false_hits"] == 0
    assert 0.85 < best["threshold"] <= 0.90


def test_threshold_scoring_counts_false_hits():
    row = score_threshold([(0.9, False), (0.9, True), (0.5, True)], 0.8)
    assert row["false_hits"] == 1
    assert row["precision"] == 0.5
    assert row["recall"] == 0.5
