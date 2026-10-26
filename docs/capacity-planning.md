# Capacity Planning (учебный стенд)

> **Smoke ≠ capacity.** [`docs/load-report.md`](load-report.md) и `scripts/load_smoke.py` измеряют потолок API+RAG на малой серии запросов. Этот документ — расчёт железа и целевой нагрузки для демо / submission-профиля.

Связанные артефакты: [ADR-001](../architecture/adr/ADR-001-llm-serving.md) · [vllm-profile](infra/vllm-profile.md) · [model-card](model-card.md) · Helm [`values.yaml`](../app/infra/helm/knowledge-platform/values.yaml).

## Целевая нагрузка (учебный / demo)

| Параметр | Desktop demo | Submission (vLLM, design) |
| -------- | ------------ | ------------------------- |
| Concurrent chat | 1–2 | до `max-num-seqs=2` |
| Chat RPS (E2E с LLM) | &lt; 1–2 | ограничено GPU KV / seqs |
| Chat RPS (API+RAG, MOCK LLM) | ~100+ (smoke) | не целевой SLO |
| Context | 2–4k tokens | 4096 |
| Semantic cache | off (default) | off рекомендуется для воспроизводимого evidence |

Узкое место продакшен-пути — **LLM Serving**, не GraphRAG/ACL слой (подтверждено MOCK smoke в load-report).

## Формулы (ориентиры)

**Веса модели (приблизительно):**

\[
\text{VRAM}_{\text{weights}} \approx N_{\text{params}} \times b_{\text{byte/param}}
\]

| Квантование | \(b\) |
| ----------- | --- |
| FP16 | ~2 |
| AWQ / INT4 | ~0.5 (+ ядра/overhead) |
| GGUF Q4 (Ollama) | ~0.5–0.6 в **системной RAM** |

**KV-cache (грубо, decoder-only):**

\[
\text{VRAM}_{\text{KV}} \propto L_{\text{layers}} \times H \times \text{ctx} \times \text{batch} \times 2 \times b_{\text{kv}}
\]

Для учебного расчёта достаточно: weights + **30–50% запас** на KV/activations при ctx 4096 и batch ≤ 2.

**Data-plane RAM (сумма requests, не peak):** взять Helm `resources.*.requests` + типовые heap datastore.

## Desktop — Ollama (`qwen2.5:0.5b`)

Измеренный host для evidence (владелец репозитория):

| Ресурс | Значение |
| ------ | -------- |
| CPU | Intel Core i7-8550U @ 1.80 GHz (4c / 8t) |
| RAM | ~32 GB |
| GPU | нет (CPU-only Ollama) |

| Компонент | Оценка footprint |
| --------- | ---------------- |
| Ollama + `qwen2.5:0.5b` (Q4 GGUF) | ~0.4–0.8 GB RAM |
| API pod/process | ≥ 256 Mi (Helm request) |
| Embeddings MOCK | пренебрежимо; LOCAL e5-small ~100–200 MB |
| Compose obs (Prom/Grafana/Tempo/Loki/Alloy) | ~1–2 GB суммарно |
| K8s data-plane (Desktop) | см. ниже |

**Вывод desktop:** 16 GB RAM достаточно для hybrid demo; 32 GB комфортно с LGTM. GPU не требуется.

## Submission — vLLM AWQ (design-time)

Профиль: [vllm-profile.md](infra/vllm-profile.md). **Runtime на этом хосте не проверен** (нет NVIDIA GPU).

| Модель | Params | Квант | VRAM weights (оценка) | + KV/запас (ctx 4096, seqs 2) | Итого VRAM |
| ------ | ------ | ----- | --------------------- | ---------------------------- | ---------- |
| `Qwen/Qwen2.5-1.5B-Instruct-AWQ` | 1.5B | AWQ ~4-bit | \(1.5 \times 0.5 \approx 0.75\) GB | ~0.5–1.0 GB | **~2–3 GB** |
| `Qwen/Qwen2.5-0.5B-Instruct` FP16 (&lt;6 GB card) | 0.5B | FP16 | \(0.5 \times 2 = 1.0\) GB | ~0.5–1.0 GB | **~2–3 GB** |

Рекомендация: карта **≥ 6 GB VRAM** с запасом под драйвер/CUDA; для &lt;6 GB — 0.5B FP16 (зафиксировать в model-card).

CPU/RAM host под vLLM: ≥ 4 vCPU, ≥ 16 GB system RAM + диск под HF cache.

## Data-plane (Helm requests / PVC)

Из [`values.yaml`](../app/infra/helm/knowledge-platform/values.yaml):

| Сервис | CPU request | Memory request | PVC |
| ------ | ----------- | -------------- | --- |
| API | 100m | 256Mi | — |
| Frontend | 50m | 64Mi | — |
| Postgres | (image default) | ~256–512 Mi typ. | 5Gi |
| Neo4j | heap ~1–2 Gi typ. | | 5Gi |
| Qdrant | ~256–512 Mi typ. | | 5Gi |
| Redis | ~64 Mi typ. | | — |
| MinIO | ~256 Mi typ. | | 10Gi |

**Суммарно (ориентир desktop K8s):** ~4–8 GB RAM data-plane + API/frontend; диск ≥ 25 Gi PVC. Это **не** кластерный capacity plan — только lab sizing.

## Связь с замерами

| Замер | Что доказывает | Что не доказывает |
| ----- | -------------- | ----------------- |
| MOCK load smoke | потолок API+GraphRAG+ACL | latency реальной модели |
| Ollama E2E smoke | p95 chat на laptop CPU | vLLM / GPU SLO |
| Capacity tables выше | выбор железа под demo/submission | автоскейлинг / multi-tenant |

Повторить Ollama E2E после `hybrid-up` + `LLM_PROVIDER=OLLAMA`; сырые JSON — в [`docs/evidence/load/`](evidence/load/).
