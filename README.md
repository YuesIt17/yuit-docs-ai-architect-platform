# RetailPartnerX Knowledge Platform (учебный MVP)

**Защищённая платформа мультимодального анализа корпоративных знаний (GraphRAG)** для курса «ИИ-архитектор».

> **Глоссарий:** [docs/Glossary.md](docs/Glossary.md) · **ADD:** [architecture/](architecture/) · **Ops:** [docs/](docs/) · **Setup:** [docs/SETUP.md](docs/SETUP.md) · **Evidence:** [docs/evidence/](docs/evidence/) · **Видео:** pending

## Что решает MVP и для кого

Сотрудники магазина, category managers и compliance RetailPartnerX получают grounded-ответы по Product/Policy KB и демо-этикеткам **в закрытом контуре** (без SaaS OpenAI/Anthropic), с ролевым ACL на уровне документов/чанков и проверяемым GraphRAG-путём (товар → аллерген → политика).

## Current vs planned

| Область | Current | Planned |
|---------|---------|---------|
| Auth | Demo Bearer roles (`DEMO_AUTH_ENABLED`) | Корпоративный IdP / JWT |
| LLM desktop | Ollama `qwen2.5:0.5b` | — |
| LLM submission | vLLM AWQ profile (см. ниже) | GPU runtime verification |
| Embeddings | MOCK (CI) / LOCAL e5-small | Offline weights path |
| OCR | **MOCK** pipeline contract | Real vision OCR (out of this MVP) |
| Vault | Stub README | Live Vault agent |
| Session memory | `session_id` only | Dialog persistence |
| Video | Script ready | Owner recording |

## Режимы запуска

| Режим | STORE | LLM | Embeddings | Cache | Когда |
|-------|-------|-----|------------|-------|-------|
| CI / unit | memory | MOCK | MOCK | off | `pytest` |
| Desktop hybrid | memory/live | OLLAMA | MOCK/LOCAL | off default | `hybrid-up` |
| Submission | live strict | VLLM | LOCAL e5-small | off default | [vllm-profile](docs/infra/vllm-profile.md) |

**vLLM GPU:** если NVIDIA GPU нет — конфигурация статическая, статус **«runtime не проверен»**.

## Requirements matrix (проверяемые критерии)

| Критерий | Статус | Проверка | Evidence |
|----------|--------|----------|----------|
| Нет облачных inference API | done | ADR-001; MOCK/OLLAMA/VLLM only | [ADR-001](architecture/adr/ADR-001-llm-serving.md) |
| Deployment + Data Flow | done | docs + diagrams | [deployment](architecture/docs/deployment.md) |
| GraphRAG path | done | `pytest tests/test_rag_graph_on_off.py` | graph-on/off |
| ACL secret deny | done | `pytest tests/test_acl.py tests/test_sec_*` | manager↛secret |
| Cache ACL revoke | done | `pytest tests/test_sec_cache_acl.py` | — |
| Asset ACL | done | `pytest tests/test_sec_assets_store.py` | guest↛internal |
| Path traversal blocked | done | same | tmp object-store |
| LangGraph state machine | done | `kp/agent/graph.py` | not ReAct |
| Observability | partial | Tempo/Loki/Alloy + domain spans | [ADR-006](architecture/adr/ADR-006-observability.md) |
| Load smoke | smoke only | `python scripts/load_smoke.py` | [load-report](docs/load-report.md) |
| Video | **pending** | [AI_PLATFORM_VIDEO_SCRIPT](tasks/AI_PLATFORM_VIDEO_SCRIPT.md) | no URL yet |
| Real OCR | **deferred** | known deviation | mock only |

Сдача: **минимум за 8 дней до защиты** (дата защиты — у владельца). Не считать MVP «готовым к сдаче», пока обязательные evidence не заполнены в `docs/evidence/`.

## Hardware / models

| Component | Default |
|-----------|---------|
| Chat desktop | Ollama `qwen2.5:0.5b` |
| Chat submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` via vLLM (AWQ, ctx 4096) — runtime may be unverified |
| Embeddings | `intfloat/multilingual-e5-small` (384) or MOCK |
| OCR | MOCK (`provider=MOCK`) |

## Структура репозитория

| Путь | Что внутри |
| ---- | ---------- |
| [`app/`](app/) | `backend/`, `frontend/`, `infra/`, `datasets/`, `scripts/` |
| [`architecture/`](architecture/) | C4 L1–L4, ADR, diagrams |
| [`architecture/diagrams/`](architecture/diagrams/) | Канонические SVG из кода |
| [`docs/`](docs/) | SETUP, SRE, infra, demo, evidence, model-card |
| [`tools/diagrams/`](tools/diagrams/) | Toolchain генерации схем |
| [`data/`](data/) | **Runtime-only** object-store (создаётся при запуске; не исходники) |
| [`tasks/`](tasks/) | Cursor fixes + video script |

## Архитектура из кода

Канонические схемы собираются из реализации (Structurizr, LangGraph, Pyreverse, Helm→KubeDiagrams), а не перерисовкой Draw.io.

```powershell
python tools/diagrams/build.py --bootstrap
python tools/diagrams/build.py --profile desktop
python tools/diagrams/build.py --profile desktop --check
```

Документация: **[docs/DIAGRAMS.md](docs/DIAGRAMS.md)** · SVG: [architecture/diagrams/images/](architecture/diagrams/images/) · workflow · C4 · code view · K8s topology.

## Быстрый старт

Полная инструкция: **[docs/SETUP.md](docs/SETUP.md)**.

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
```

```bash
bash app/scripts/hybrid/hybrid-up.sh
cd app/backend && .venv/Scripts/python -m pytest -q   # Windows venv
```

Demo auth (не production IdP): Bearer `guest` | `associate` | `manager` | `compliance`.

## Известные отклонения

1. **OCR = MOCK** — демонстрация контракта пайплайна, не распознавание реального скана. Согласование real OCR с преподавателем — отдельно.
2. **Demo-auth** — учебные Bearer-токены.
3. **vLLM runtime** — может быть «не проверен» без GPU.
4. **Vault** — planned stub.
5. **Видео** — pending до записи владельцем.

## Автор

**Евгений Юлов** — Platform Engineer / AI Architect (учебный case study).

GitHub: [YuesIt17/yuit-docs-ai-architect-platform](https://github.com/YuesIt17/yuit-docs-ai-architect-platform)
