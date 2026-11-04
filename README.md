# RetailPartnerX Knowledge Platform (learning MVP)

**A secure platform for multimodal analysis of corporate knowledge (GraphRAG)**, built for the AI Architect course.

> **Glossary:** [docs/Glossary.md](docs/Glossary.md) · **ADD:** [architecture/](architecture/) · **Setup:** [docs/SETUP.md](docs/SETUP.md) · **Evidence:** [docs/evidence/](docs/evidence/) · **Video (Russian narration):** [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU)

RetailPartnerX store associates, category managers and compliance officers get grounded answers from the Product/Policy KB and demo labels **inside a closed perimeter** (no SaaS OpenAI/Anthropic), with role-based ACL and a verifiable GraphRAG path (product → allergen → policy).

[![Project demo · YouTube](https://img.youtube.com/vi/y2_mY9_ceuU/hqdefault.jpg)](https://www.youtube.com/watch?v=y2_mY9_ceuU)

---

## Course submission: minimum requirements

These criteria come from the course submission form. Everything else in the repository is **additional functionality** (see below).

### 1. Git monorepo

| Requirement | Where | Status |
| ----------- | ----- | ------ |
| `/infra`: docker-compose or Helm | [`app/infra/`](app/infra/) (`docker-compose.yml`, Helm chart) | done |
| `/backend`: agents and API | [`app/backend/`](app/backend/) (`kp/agent`, `kp/api`) | done |
| `/docs`: ADD (Markdown / PDF) | [`docs/`](docs/) · ADD [`architecture/`](architecture/) | done |

> The paths are nested under `app/` (a convenient monorepo with backend, frontend and infra side by side). The criterion's content is covered; there are no literal `/infra` and `/backend` folders at the root.

### 2. Architecture Design Document (ADD)

| Requirement | Where | Status |
| ----------- | ----- | ------ |
| Full set of diagrams (UML / C4) | [`architecture/diagrams/`](architecture/diagrams/) · [`docs/DIAGRAMS.md`](docs/DIAGRAMS.md) · C4 L1–L4 [`architecture/docs/`](architecture/docs/) | done |
| Capacity Planning section | [`docs/capacity-planning.md`](docs/capacity-planning.md) | done |
| Hardware sizing: VRAM, CPU, RAM | [`docs/capacity-planning.md`](docs/capacity-planning.md) (desktop Ollama + submission vLLM AWQ) | done |

### 3. Deep-dive demo and load report

| Requirement | Where | Status |
| ----------- | ----- | ------ |
| 5–7 min video | [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU) · script [`tasks/defense-video-script.md`](tasks/defense-video-script.md) · URL in [`docs/evidence/manifest.json`](docs/evidence/manifest.json) | done |
| Jaeger traces / vLLM logs | [`docs/evidence/trace.md`](docs/evidence/trace.md) (Tempo ≈ Jaeger) · [`docs/evidence/loki.md`](docs/evidence/loki.md) (Ollama) · [`ADR-006`](architecture/adr/ADR-006-observability.md) · [`vllm-profile`](docs/infra/vllm-profile.md) | done* |
| Neo4j graph visualization | [`GraphPage.tsx`](app/frontend/src/pages/GraphPage.tsx) (ACL subgraph SVG) · [`docs/SETUP.md`](docs/SETUP.md) (Browser `:30474`) · [`demo_graph.cypher`](app/scripts/demo_graph.cypher) · [`ADR-003`](architecture/adr/ADR-003-graph-db.md) | done |
| Load report: RPS and latency | [`docs/load-report.md`](docs/load-report.md) · [`docs/evidence/load/`](docs/evidence/load/) | done |

\* Desktop evidence is Ollama in Loki/Tempo. Without NVIDIA, the vLLM **runtime is not verified** ([`vllm-profile`](docs/infra/vllm-profile.md)).

| Summary | Status |
| ------- | ------ |
| Git monorepo | done |
| ADD | done |
| Demo & Load | done |

---

## Additional functionality (beyond the form)

Features of the learning MVP beyond the submission form. They are useful for the demo but are **not** part of the three sections above.

| Area | What exists | Evidence / code |
| ---- | ----------- | --------------- |
| Closed LLM perimeter | MOCK / Ollama / vLLM only, no SaaS | [ADR-001](architecture/adr/ADR-001-llm-serving.md) |
| GraphRAG on/off | verifiable product→policy path | `pytest tests/test_rag_graph_on_off.py` |
| ACL / security | secret deny, cache revoke, asset ACL, path traversal | `tests/test_acl.py`, `tests/test_sec_*` |
| LangGraph | state machine, not ReAct | `kp/agent/graph.py` |
| Frontend | Chat, Graph, Labels, Ops, LLM settings | `app/frontend/` |
| Hybrid desktop | K8s data plane + Compose LLM/obs | `app/scripts/hybrid/` |
| Observability LGTM | Grafana / Prometheus / Loki / Tempo | [ADR-006](architecture/adr/ADR-006-observability.md) |
| Model Card / SRE / Setup | ops documentation | [docs/](docs/) |
| Label OCR | **MOCK** pipeline contract (real OCR deferred) | ADR-007 |
| Demo auth | Bearer roles (not an IdP) | `DEMO_AUTH_ENABLED` |
| Vault | stub | `app/infra/vault/` |

### Current state vs plan (additional functionality)

| Area | Now | Plan |
|------|-----|------|
| Auth | Demo Bearer | Corporate IdP / JWT |
| LLM desktop | Ollama `qwen2.5:0.5b` | — |
| LLM submission | vLLM AWQ profile | runtime on a GPU |
| Embeddings | MOCK (CI) / LOCAL e5-small | Offline weights path |
| OCR | MOCK | Real vision OCR (outside the MVP) |
| Vault | Stub README | Live Vault agent |
| Session memory | `session_id` only | Dialog persistence |
| Video | [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU) · `video_url` in the manifest | — |

---

## Run modes

| Mode | STORE | LLM | Embeddings | Cache | When |
|------|-------|-----|------------|-------|------|
| CI / unit | memory | MOCK | MOCK | off | `pytest` |
| Desktop hybrid | memory/live | OLLAMA | MOCK/LOCAL | off default | `hybrid-up` |
| Submission | live strict | VLLM | LOCAL e5-small | off default | [vllm-profile](docs/infra/vllm-profile.md) |

**vLLM GPU:** without NVIDIA, the configuration is static and its status is **"runtime not verified"**.

## Hardware / models

Calculations: **[docs/capacity-planning.md](docs/capacity-planning.md)**.

| Component | Default |
|-----------|---------|
| Chat desktop | Ollama `qwen2.5:0.5b` |
| Chat submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` via vLLM (AWQ, ctx 4096) |
| Embeddings | `intfloat/multilingual-e5-small` (384) or MOCK |
| OCR | MOCK (`provider=MOCK`) |

## Repository structure

| Path | Contents | Link to the form |
| ---- | -------- | ---------------- |
| [`app/infra/`](app/infra/) | Compose + Helm | ≈ `/infra` |
| [`app/backend/`](app/backend/) | Agents + API | ≈ `/backend` |
| [`app/frontend/`](app/frontend/) | UI | additional |
| [`docs/`](docs/) | SETUP, capacity, load, evidence | `/docs` |
| [`architecture/`](architecture/) | ADD: C4, ADR, diagrams | ADD |
| [`tools/diagrams/`](tools/diagrams/) | diagram generation from code | additional |
| [`tasks/`](tasks/) | video script | demo |
| [`data/`](data/) | runtime object store (not source) | — |

## Architecture from code

Canonical diagrams are built from the implementation (Structurizr, LangGraph, Pyreverse, Helm→KubeDiagrams).

```powershell
python tools/diagrams/build.py --bootstrap
python tools/diagrams/build.py --profile desktop
python tools/diagrams/build.py --profile desktop --check
```

Documentation: **[docs/DIAGRAMS.md](docs/DIAGRAMS.md)** · SVG: [architecture/diagrams/images/](architecture/diagrams/images/).

## Quick start

Full instructions: **[docs/SETUP.md](docs/SETUP.md)**.

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
```

```bash
bash app/scripts/hybrid/hybrid-up.sh
cd app/backend && .venv/Scripts/python -m pytest -q   # Windows venv
```

Demo auth: Bearer `guest` | `associate` | `manager` | `compliance`.

## Known deviations

1. **Monorepo paths:** `app/infra`, `app/backend` instead of root `/infra`, `/backend`.
2. **Observability:** Tempo instead of Jaeger; Ollama logs instead of vLLM (no GPU).
3. **OCR = MOCK:** a pipeline contract, not real vision.
4. **Demo auth:** learning Bearer tokens.
5. **Vault:** planned stub.
6. **vLLM GPU:** the profile exists, but its runtime is not verified on this setup.

## Author

**Evgeny Yulov**, Platform Engineer / AI Architect (learning case study).

GitHub: [YuesIt17/yuit-docs-ai-architect-platform](https://github.com/YuesIt17/yuit-docs-ai-architect-platform)
