"""Simple load smoke for load report."""

from __future__ import annotations

import asyncio
import statistics
import time

import httpx

BASE = "http://127.0.0.1:8080"
N = 20


async def main() -> None:
    latencies: list[float] = []
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
        # warmup
        await client.get(f"{BASE}/health")
        for i in range(N):
            t0 = time.perf_counter()
            r = await client.post(
                f"{BASE}/v1/chat",
                headers={"Authorization": "Bearer manager"},
                json={"message": "Какие аллергены у FreshFarm oats?", "stream": False},
            )
            r.raise_for_status()
            latencies.append((time.perf_counter() - t0) * 1000)
        elapsed = sum(latencies) / 1000
        rps = N / elapsed if elapsed else 0
        p95 = sorted(latencies)[int(0.95 * (N - 1))]
        print(f"requests={N}")
        print(f"rps~={rps:.2f}")
        print(f"latency_ms avg={statistics.mean(latencies):.1f} p95={p95:.1f} max={max(latencies):.1f}")
        Path = __import__("pathlib").Path
        report = Path(__file__).resolve().parents[2] / "docs" / "load-report.md"
        report.write_text(
            "# Load Report (smoke)\n\n"
            f"| Metric | Value | Hardware |\n|--------|-------|----------|\n"
            f"| RPS | {rps:.2f} | local MOCK LLM |\n"
            f"| Latency avg ms | {statistics.mean(latencies):.1f} | |\n"
            f"| Latency p95 ms | {p95:.1f} | |\n"
            f"| LLM provider | MOCK | |\n"
            f"| Requests | {N} | GraphRAG in-process |\n",
            encoding="utf-8",
        )
        print(f"wrote {report}")


if __name__ == "__main__":
    asyncio.run(main())