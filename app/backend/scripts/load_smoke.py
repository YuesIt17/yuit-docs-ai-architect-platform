"""Parameterized load smoke (not a capacity test). Writes docs/load-report.md + raw JSON."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
QUESTIONS = [
    "Какие аллергены у FreshFarm oats?",
    "Что говорит политика про gluten и nuts?",
    "Расскажи про творог Простоквашино",
    "Какие требования к маркировке молока?",
    "Shelf labeling policy allergens",
]


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, int(p * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


async def run_once(client: httpx.AsyncClient, base: str, token: str, message: str) -> dict:
    t0 = time.perf_counter()
    err = None
    status = 0
    try:
        r = await client.post(
            f"{base}/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": message, "stream": False},
        )
        status = r.status_code
        r.raise_for_status()
        body = r.json()
        acl = body.get("acl_decision")
        provider = body.get("llm_provider")
    except Exception as exc:
        err = f"{exc.__class__.__name__}: {exc}"
        acl = None
        provider = None
    ms = (time.perf_counter() - t0) * 1000
    return {
        "latency_ms": ms,
        "ok": err is None,
        "status": status,
        "error": err,
        "acl_decision": acl,
        "llm_provider": provider,
        "message": message,
    }


async def main() -> None:
    p = argparse.ArgumentParser(description="KP load smoke (sequential or lightly concurrent)")
    p.add_argument("--base-url", default="http://127.0.0.1:8080")
    p.add_argument("--token", default="manager")
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--concurrency", type=int, default=1)
    p.add_argument(
        "--scenario",
        choices=["cache_miss", "cache_hit", "mixed"],
        default="cache_miss",
        help="cache_hit reuses one question; cache_miss rotates questions",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    results: list[dict] = []
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        health = await client.get(f"{args.base_url}/health")
        health.raise_for_status()
        health_json = health.json()
        # warmup
        await run_once(client, args.base_url, args.token, QUESTIONS[0])

        sem = asyncio.Semaphore(max(1, args.concurrency))

        async def bounded(i: int) -> dict:
            async with sem:
                if args.scenario == "cache_hit":
                    msg = QUESTIONS[0]
                else:
                    msg = QUESTIONS[i % len(QUESTIONS)]
                return await run_once(client, args.base_url, args.token, msg)

        results = await asyncio.gather(*[bounded(i) for i in range(args.count)])

    ok = [r for r in results if r["ok"]]
    lat = sorted(r["latency_ms"] for r in ok)
    elapsed_s = sum(r["latency_ms"] for r in results) / 1000.0
    rps = (len(results) / elapsed_s) if elapsed_s else 0.0
    success_rate = len(ok) / len(results) if results else 0.0

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "scenario": args.scenario,
        "count": args.count,
        "concurrency": args.concurrency,
        "seed": args.seed,
        "note": "smoke only — not a capacity / scaling limit test",
        "health": health_json,
        "success_rate": success_rate,
        "error_rate": 1.0 - success_rate,
        "rps_approx": rps,
        "latency_ms": {
            "p50": percentile(lat, 0.50),
            "p95": percentile(lat, 0.95),
            "p99": percentile(lat, 0.99),
            "avg": statistics.mean(lat) if lat else 0.0,
            "max": max(lat) if lat else 0.0,
        },
        "results": results,
    }

    raw_dir = ROOT / "docs" / "evidence" / "load"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"smoke_{args.scenario}_{args.count}x{args.concurrency}.json"
    raw_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    provider = health_json.get("llm_provider", "unknown")
    report = ROOT / "docs" / "load-report.md"
    report.write_text(
        "# Load Report (smoke)\n\n"
        "> 20 sequential (or low-concurrency) requests = **smoke**, not a capacity test. "
        "Do not extrapolate scaling limits from this run.\n\n"
        f"| Field | Value |\n|-------|-------|\n"
        f"| Generated | {meta['generated_at']} |\n"
        f"| Scenario | `{args.scenario}` |\n"
        f"| Base URL | `{args.base_url}` |\n"
        f"| Count / concurrency | {args.count} / {args.concurrency} |\n"
        f"| Success rate | {success_rate:.2%} |\n"
        f"| RPS (approx) | {rps:.2f} |\n"
        f"| Latency p50 / p95 / p99 ms | "
        f"{meta['latency_ms']['p50']:.1f} / {meta['latency_ms']['p95']:.1f} / {meta['latency_ms']['p99']:.1f} |\n"
        f"| Effective LLM (from /health) | `{provider}` |\n"
        f"| Store backend | `{health_json.get('store_backend')}` |\n"
        f"| Index version | `{health_json.get('index_version')}` |\n"
        f"| Raw results | `{raw_path.relative_to(ROOT).as_posix()}` |\n"
        f"| Tokens/s / TTFT | not measured in this smoke |\n",
        encoding="utf-8",
    )
    print(json.dumps({k: meta[k] for k in ("scenario", "rps_approx", "success_rate", "latency_ms")}, indent=2))
    print(f"wrote {report}")
    print(f"wrote {raw_path}")


if __name__ == "__main__":
    asyncio.run(main())
