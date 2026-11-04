# Capacity Planning (lab environment)

> **A smoke test is not a capacity test.** [`docs/load-report.md`](load-report.md) and `scripts/load_smoke.py` measure the API+RAG ceiling on a small series of requests. This document covers hardware sizing and target load for the demo and submission profiles.

Related artifacts: [ADR-001](../architecture/adr/ADR-001-llm-serving.md) · [vllm-profile](infra/vllm-profile.md) · [model-card](model-card.md) · Helm [`values.yaml`](../app/infra/helm/knowledge-platform/values.yaml).

## Target load (learning / demo)

| Parameter | Desktop demo | Submission (vLLM, design) |
| --------- | ------------ | ------------------------- |
| Concurrent chat | 1–2 | up to `max-num-seqs=2` |
| Chat RPS (E2E with LLM) | &lt; 1–2 | limited by GPU KV / seqs |
| Chat RPS (API+RAG, MOCK LLM) | ~100+ (smoke) | not a target SLO |
| Context | 2–4k tokens | 4096 |
| Semantic cache | off (default) | off recommended for reproducible evidence |

The bottleneck on the production path is **LLM Serving**, not the GraphRAG/ACL layer (confirmed by the MOCK smoke test in the load report).

## Formulas (rough guides)

**Model weights (approximate):**

\[
\text{VRAM}_{\text{weights}} \approx N_{\text{params}} \times b_{\text{byte/param}}
\]

| Quantization | \(b\) |
| ------------ | --- |
| FP16 | ~2 |
| AWQ / INT4 | ~0.5 (+ kernels/overhead) |
| GGUF Q4 (Ollama) | ~0.5–0.6 in **system RAM** |

**KV cache (rough, decoder-only):**

\[
\text{VRAM}_{\text{KV}} \propto L_{\text{layers}} \times H \times \text{ctx} \times \text{batch} \times 2 \times b_{\text{kv}}
\]

For a learning estimate, weights plus a **30–50% margin** for KV/activations is enough at ctx 4096 and batch ≤ 2.

**Data-plane RAM (sum of requests, not peak):** take Helm `resources.*.requests` plus typical datastore heaps.

## Desktop — Ollama (`qwen2.5:0.5b`)

Measured host for the evidence (repository owner's machine):

| Resource | Value |
| -------- | ----- |
| CPU | Intel Core i7-8550U @ 1.80 GHz (4c / 8t) |
| RAM | ~32 GB |
| GPU | none (CPU-only Ollama) |

| Component | Estimated footprint |
| --------- | ------------------- |
| Ollama + `qwen2.5:0.5b` (Q4 GGUF) | ~0.4–0.8 GB RAM |
| API pod/process | ≥ 256 Mi (Helm request) |
| Embeddings MOCK | negligible; LOCAL e5-small ~100–200 MB |
| Compose obs (Prom/Grafana/Tempo/Loki/Alloy) | ~1–2 GB total |
| K8s data plane (Desktop) | see below |

**Desktop conclusion:** 16 GB RAM is enough for the hybrid demo; 32 GB is comfortable with LGTM. No GPU is required.

## Submission — vLLM AWQ (design time)

Profile: [vllm-profile.md](infra/vllm-profile.md). **Runtime not verified on this host** (no NVIDIA GPU).

| Model | Params | Quant | VRAM weights (estimate) | + KV/margin (ctx 4096, seqs 2) | Total VRAM |
| ----- | ------ | ----- | ----------------------- | ------------------------------ | ---------- |
| `Qwen/Qwen2.5-1.5B-Instruct-AWQ` | 1.5B | AWQ ~4-bit | \(1.5 \times 0.5 \approx 0.75\) GB | ~0.5–1.0 GB | **~2–3 GB** |
| `Qwen/Qwen2.5-0.5B-Instruct` FP16 (&lt;6 GB card) | 0.5B | FP16 | \(0.5 \times 2 = 1.0\) GB | ~0.5–1.0 GB | **~2–3 GB** |

Recommendation: a card with **≥ 6 GB VRAM**, leaving headroom for the driver/CUDA; for &lt;6 GB, use 0.5B FP16 (record this in the model card).

vLLM host CPU/RAM: ≥ 4 vCPU, ≥ 16 GB system RAM, plus disk for the HF cache.

## Data plane (Helm requests / PVC)

From [`values.yaml`](../app/infra/helm/knowledge-platform/values.yaml):

| Service | CPU request | Memory request | PVC |
| ------- | ----------- | -------------- | --- |
| API | 100m | 256Mi | — |
| Frontend | 50m | 64Mi | — |
| Postgres | (image default) | ~256–512 Mi typ. | 5Gi |
| Neo4j | heap ~1–2 Gi typ. | | 5Gi |
| Qdrant | ~256–512 Mi typ. | | 5Gi |
| Redis | ~64 Mi typ. | | — |
| MinIO | ~256 Mi typ. | | 10Gi |

**Total (desktop K8s guide):** ~4–8 GB RAM for the data plane + API/frontend; disk ≥ 25 Gi PVC. This is **not** a cluster capacity plan, only lab sizing.

## Link to measurements

| Measurement | What it proves | What it does not prove |
| ----------- | -------------- | ---------------------- |
| MOCK load smoke | API+GraphRAG+ACL ceiling | real model latency |
| Ollama E2E smoke | chat p95 on a laptop CPU | vLLM / GPU SLO |
| Capacity tables above | hardware choice for demo/submission | autoscaling / multi-tenancy |

Repeat the Ollama E2E run after `hybrid-up` with `LLM_PROVIDER=OLLAMA`; raw JSON is in [`docs/evidence/load/`](evidence/load/).
