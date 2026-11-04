#!/usr/bin/env python3
"""Measure TTFT and throughput of an OpenAI-compatible server across parallel sequences.

Run on the GPU host. Results are written to docs/evidence/load/ and describe that host only:
  python scripts/bench_vllm.py --model Qwen/Qwen2.5-1.5B-Instruct-AWQ --concurrency 1 2 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

REPO = Path(__file__).resolve().parents[3]
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "vllm"}
PROMPT = (
    "You are a retail compliance assistant. Explain in about 120 words why products containing "
    "gluten and nuts must show allergen icons on shelf labels."
)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * p / 100), len(ordered) - 1)]


async def one_request(client: httpx.AsyncClient, url: str, model: str, max_tokens: int) -> dict:
    """Count tokens from usage when the server reports it, and from stream chunks otherwise."""
    body = {
        "model": model,
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": PROMPT}],
    }
    started = time.perf_counter()
    first_token = None
    chunks = 0
    usage_tokens = None
    try:
        async with client.stream("POST", url, json=body) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line.endswith("[DONE]"):
                    continue
                payload = json.loads(line[6:])
                if payload.get("usage"):
                    usage_tokens = payload["usage"].get("completion_tokens")
                choices = payload.get("choices") or []
                if choices and choices[0].get("delta", {}).get("content"):
                    first_token = first_token or time.perf_counter()
                    chunks += 1
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": exc.__class__.__name__}
    if first_token is None:
        return {"ok": False, "error": "NoTokens"}
    return {
        "ok": True,
        "ttft_s": first_token - started,
        "total_s": time.perf_counter() - started,
        "tokens": usage_tokens or chunks,
    }


async def run_level(client, url: str, model: str, concurrency: int, requests: int, max_tokens: int) -> dict:
    limiter = asyncio.Semaphore(concurrency)

    async def limited() -> dict:
        async with limiter:
            return await one_request(client, url, model, max_tokens)

    started = time.perf_counter()
    results = await asyncio.gather(*(limited() for _ in range(requests)))
    wall = time.perf_counter() - started
    ok = [r for r in results if r["ok"]]
    ttfts = [r["ttft_s"] for r in ok]
    return {
        "concurrency": concurrency,
        "requests": requests,
        "succeeded": len(ok),
        "errors": sorted({r["error"] for r in results if not r["ok"]}),
        "ttft_p50_s": percentile(ttfts, 50),
        "ttft_p95_s": percentile(ttfts, 95),
        "total_p95_s": percentile([r["total_s"] for r in ok], 95),
        "tokens_per_s": sum(r["tokens"] for r in ok) / wall if wall else 0.0,
    }


async def bench(base_url: str, model: str, levels: list[int], requests: int, max_tokens: int, transport=None) -> dict:
    url = f"{base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=600.0, trust_env=False, transport=transport) as client:
        results = [await run_level(client, url, model, level, requests, max_tokens) for level in levels]
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "model": model,
        "max_tokens": max_tokens,
        "levels": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4])
    parser.add_argument("--requests", type=int, default=20, help="requests per concurrency level")
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--label", default="vllm", help="used in the output filename")
    args = parser.parse_args(argv)

    if urlparse(args.base_url).hostname not in LOCAL_HOSTS:
        print(f"Refusing non-local base URL: {args.base_url}", file=sys.stderr)
        return 2
    report = asyncio.run(bench(args.base_url, args.model, args.concurrency, args.requests, args.max_tokens))
    text = json.dumps(report, indent=2)
    print(text)
    out = REPO / "docs" / "evidence" / "load" / f"bench_{args.label}.json"
    out.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {out}", file=sys.stderr)
    return 0 if all(level["succeeded"] for level in report["levels"]) else 1


if __name__ == "__main__":
    sys.exit(main())
