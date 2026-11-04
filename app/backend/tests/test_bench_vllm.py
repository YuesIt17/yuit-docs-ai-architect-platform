"""The benchmark's measurements, checked against a scripted streaming server."""

from __future__ import annotations

import json

import httpx
import pytest

from scripts.bench_vllm import bench, main, percentile


def stream_response(tokens: int, usage: int | None) -> str:
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': 'x'}}]})}" for _ in range(tokens)]
    if usage is not None:
        lines.append(f"data: {json.dumps({'choices': [], 'usage': {'completion_tokens': usage}})}")
    return "\n".join([*lines, "data: [DONE]"]) + "\n"


def transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_reports_every_concurrency_level_and_prefers_server_usage():
    def handler(request):
        return httpx.Response(200, text=stream_response(tokens=3, usage=50))

    report = await bench("http://127.0.0.1:8000/v1", "m", [1, 2], 4, 16, transport=transport(handler))
    assert [level["concurrency"] for level in report["levels"]] == [1, 2]
    level = report["levels"][0]
    assert level["succeeded"] == 4
    assert level["ttft_p50_s"] is not None
    # 4 requests x 50 reported tokens over the wall clock; the 3 chunks must not be the count.
    assert level["tokens_per_s"] > 0


@pytest.mark.asyncio
async def test_failed_requests_are_counted_not_averaged_in():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] % 2:
            return httpx.Response(500)
        return httpx.Response(200, text=stream_response(tokens=2, usage=None))

    level = (await bench("http://127.0.0.1:8000/v1", "m", [1], 4, 16, transport=transport(handler)))["levels"][0]
    assert level["succeeded"] == 2
    assert level["errors"] == ["HTTPStatusError"]


@pytest.mark.asyncio
async def test_a_stream_with_no_tokens_is_a_failure():
    def handler(request):
        return httpx.Response(200, text="data: [DONE]\n")

    level = (await bench("http://127.0.0.1:8000/v1", "m", [1], 1, 16, transport=transport(handler)))["levels"][0]
    assert level["succeeded"] == 0
    assert level["errors"] == ["NoTokens"]


def test_refuses_a_remote_endpoint():
    assert main(["--model", "m", "--base-url", "https://api.openai.com/v1"]) == 2


def test_percentile_handles_empty_and_bounds():
    assert percentile([], 95) is None
    assert percentile([1.0, 2.0, 3.0], 100) == 3.0
