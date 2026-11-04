# Load Report

> Smoke measurements from a learning environment. This is **not** a production SLO and does not replace a GPU/vLLM test bench. See [capacity-planning.md](capacity-planning.md).

Raw JSON: [`docs/evidence/load/`](evidence/load/). These files are unmodified captures, so they contain the Russian-language test questions used when the measurements were taken.

## 1. MOCK smoke (baseline API + GraphRAG + ACL)

| Parameter | Value |
| --------- | ----- |
| Scenario | GraphRAG chat path, ACL on |
| LLM | MOCK (no generation) |
| Requests / concurrency | 20 / 1 |
| Goal | API+RAG ceiling without a GPU |

| Metric | Value | Conditions |
| ------ | ----- | ---------- |
| RPS (approx) | ~79.5 | local uvicorn MOCK · 2026-10-26 |
| Latency avg | ~12.6 ms | |
| Latency p50 / p95 | ~12.0 / ~15.8 ms | |
| Success rate | 100% | 20 / 1 |
| Raw | [`evidence/load/smoke_mock_20x1.json`](evidence/load/smoke_mock_20x1.json) | |

Repeat: `python app/backend/scripts/load_smoke.py --label mock --count 20` (against a live API with `LLM_PROVIDER=MOCK`).

## 2. Ollama E2E (desktop)

| Parameter | Value |
| --------- | ----- |
| Scenario | HTTP `/v1/chat` E2E (live store + Ollama) |
| LLM | Ollama `qwen2.5:0.5b` (Q4_K_M) |
| Hardware | see capacity-planning (i7-8550U, ~32 GB RAM, CPU-only) |
| Captured | 2026-10-26 after `hybrid-up` |
| Source | `load_smoke.py` → NodePort `:30080` |

```bash
python app/backend/scripts/load_smoke.py \
  --base-url http://127.0.0.1:30080 \
  --count 10 --concurrency 1 --label ollama --timeout 180
```

> The run took about 16 minutes. On CPU, some requests hit a timeout or long generation, so the success rate is 50%. The latency below covers **successful** responses only.

| Metric | Value | Note |
| ------ | ----- | ---- |
| RPS (approx) | ~0.011 | wall clock, including errors |
| Latency avg (ok) | ~7.1 s | CPU 0.5B |
| Latency p50 / p95 (ok) | ~1.3 / ~14.1 s | |
| Latency max (ok) | ~20.1 s | |
| Success rate | 50% (5/10) | timeout / long generation |
| Raw JSON | [`evidence/load/smoke_ollama_10x1.json`](evidence/load/smoke_ollama_10x1.json) | |

Additional audit samples: [`smoke_ollama_7x1.json`](evidence/load/smoke_ollama_7x1.json).

Conclusion for §2: E2E chat on desktop Ollama takes **seconds**, not the milliseconds of MOCK; the bottleneck is the LLM.

## 3. Scenarios (design)

| Scenario | What is measured | Comment |
| -------- | ---------------- | ------- |
| Chat FAQ (MOCK) | RPS / p95 API+RAG | §1 |
| Chat + ACL deny | filter correctness | functional, not RPS |
| Label mock OCR | p95 vision path | design target &lt; 1 s |
| Chat + Ollama | tokens/s, p95 E2E | §2 |
| vLLM GPU | RPS / p95 | **runtime not verified** without NVIDIA |

## Conclusion

The MOCK+memory smoke test at 20×1 reaches about **~80 req/s** with p95 **~16 ms**. This is **not** the performance limit of Neo4j/Qdrant and not a capacity test. On desktop Ollama, `load_smoke` at 10×1 completed **5/10** requests (avg/p95 for successful ones only: **~7.1 / ~14 s**), and **5/10** ended in a ReadTimeout of ~180 s, so this setup cannot be considered stable. For the GPU submission profile, repeat on vLLM AWQ (see [vllm-profile](infra/vllm-profile.md)); until verified, the status is **runtime not verified**.
