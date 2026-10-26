# RetailPartnerX Knowledge Platform (учебный MVP)

**Защищённая платформа мультимодального анализа корпоративных знаний (GraphRAG)** для курса «ИИ-архитектор».

> **Глоссарий:** [docs/Glossary.md](docs/Glossary.md) · **ADD:** [architecture/](architecture/) · **Setup:** [docs/SETUP.md](docs/SETUP.md) · **Evidence:** [docs/evidence/](docs/evidence/) · **Видео:** ожидается

Сотрудники магазина, category managers и compliance RetailPartnerX получают grounded-ответы по Product/Policy KB и демо-этикеткам **в закрытом контуре** (без SaaS OpenAI/Anthropic), с ролевым ACL и проверяемым GraphRAG-путём (товар → аллерген → политика).

---

## Форма сдачи — минимальные требования

Критерии с формы сдачи курса. Всё остальное в репозитории — **дополнительный функционал** (см. ниже).

### 1. Git-Monorepo

| Требование формы | Где | Статус |
| ---------------- | --- | ------ |
| `/infra` — docker-compose или Helm | [`app/infra/`](app/infra/) (`docker-compose.yml`, Helm chart) | готово |
| `/backend` — агенты и API | [`app/backend/`](app/backend/) (`kp/agent`, `kp/api`) | готово |
| `/docs` — ADD (Markdown / PDF) | [`docs/`](docs/) · ADD [`architecture/`](architecture/) | готово |

> Пути вложены под `app/` (удобный monorepo: backend + frontend + infra рядом). Содержимое критерия закрыто; буквальных `/infra` и `/backend` на корне нет.

### 2. Architecture Design Document (ADD)

| Требование формы | Где | Статус |
| ---------------- | --- | ------ |
| Полный набор диаграмм (UML / C4) | [`architecture/diagrams/`](architecture/diagrams/) · [`docs/DIAGRAMS.md`](docs/DIAGRAMS.md) · C4 L1–L4 [`architecture/docs/`](architecture/docs/) | готово |
| Раздел Capacity Planning | [`docs/capacity-planning.md`](docs/capacity-planning.md) | готово |
| Расчёт железа: VRAM, CPU, RAM | [`docs/capacity-planning.md`](docs/capacity-planning.md) (desktop Ollama + submission vLLM AWQ) | готово |

### 3. Deep-Dive Demo & Load Report

| Требование формы | Где | Статус |
| ---------------- | --- | ------ |
| Видео 5–7 мин | [`tasks/AI_PLATFORM_VIDEO_SCRIPT.md`](tasks/AI_PLATFORM_VIDEO_SCRIPT.md) · URL в [`docs/evidence/manifest.json`](docs/evidence/manifest.json) | **ожидается** |
| Трейсы Jaeger / логи vLLM | [`docs/evidence/trace.md`](docs/evidence/trace.md) (Tempo ≈ Jaeger) · [`docs/evidence/loki.md`](docs/evidence/loki.md) (Ollama) · [`ADR-006`](architecture/adr/ADR-006-observability.md) · [`vllm-profile`](docs/infra/vllm-profile.md) | готово* |
| Визуализация графа Neo4j | [`GraphPage.tsx`](app/frontend/src/pages/GraphPage.tsx) (ACL subgraph SVG) · [`docs/SETUP.md`](docs/SETUP.md) (Browser `:30474`) · [`demo_graph.cypher`](app/scripts/demo_graph.cypher) · [`ADR-003`](architecture/adr/ADR-003-graph-db.md) | готово |
| Нагрузочный отчёт: RPS и латентность | [`docs/load-report.md`](docs/load-report.md) · [`docs/evidence/load/`](docs/evidence/load/) | готово |

\* Desktop evidence = Ollama в Loki/Tempo. Без NVIDIA — vLLM **runtime не проверен** ([`vllm-profile`](docs/infra/vllm-profile.md)).

| Сводно по форме | Статус |
| --------------- | ------ |
| Git-Monorepo | готово |
| ADD | готово |
| Demo & Load | видео — единственный открытый пункт |

---

## Дополнительный функционал (не критерии формы)

Фичи учебного MVP сверх формы сдачи — полезны на защите, но **не** входят в три блока выше.

| Область | Что есть | Evidence / код |
| ------- | -------- | -------------- |
| Закрытый контур LLM | только MOCK / Ollama / vLLM, без SaaS | [ADR-001](architecture/adr/ADR-001-llm-serving.md) |
| GraphRAG on/off | проверяемый путь товар→политика | `pytest tests/test_rag_graph_on_off.py` |
| ACL / security | secret deny, cache revoke, asset ACL, path traversal | `tests/test_acl.py`, `tests/test_sec_*` |
| LangGraph | state machine, не ReAct | `kp/agent/graph.py` |
| Frontend | Chat, Graph, Labels, Ops, LLM settings | `app/frontend/` |
| Hybrid desktop | K8s data-plane + Compose LLM/obs | `app/scripts/hybrid/` |
| Observability LGTM | Grafana / Prometheus / Loki / Tempo | [ADR-006](architecture/adr/ADR-006-observability.md) |
| Model Card / SRE / Setup | ops-документация | [docs/](docs/) |
| OCR этикеток | контракт пайплайна **MOCK** (real OCR отложен) | ADR-007 |
| Demo-auth | Bearer roles (не IdP) | `DEMO_AUTH_ENABLED` |
| Vault | stub | `app/infra/vault/` |

### Сейчас vs план (доп. функционал)

| Область | Сейчас | План |
|---------|--------|------|
| Auth | Demo Bearer | Корпоративный IdP / JWT |
| LLM desktop | Ollama `qwen2.5:0.5b` | — |
| LLM submission | профиль vLLM AWQ | runtime на GPU |
| Embeddings | MOCK (CI) / LOCAL e5-small | Offline weights path |
| OCR | MOCK | Real vision OCR (вне MVP) |
| Vault | Stub README | Live Vault agent |
| Session memory | только `session_id` | Dialog persistence |
| Видео | сценарий готов | запись + `video_url` (**блокер сдачи**) |

---

## Режимы запуска

| Режим | STORE | LLM | Embeddings | Cache | Когда |
|-------|-------|-----|------------|-------|-------|
| CI / unit | memory | MOCK | MOCK | off | `pytest` |
| Desktop hybrid | memory/live | OLLAMA | MOCK/LOCAL | off default | `hybrid-up` |
| Submission | live strict | VLLM | LOCAL e5-small | off default | [vllm-profile](docs/infra/vllm-profile.md) |

**vLLM GPU:** без NVIDIA — статическая конфигурация, статус **«runtime не проверен»**.

## Железо / модели

Расчёты: **[docs/capacity-planning.md](docs/capacity-planning.md)**.

| Компонент | По умолчанию |
|-----------|--------------|
| Chat desktop | Ollama `qwen2.5:0.5b` |
| Chat submission | `Qwen/Qwen2.5-1.5B-Instruct-AWQ` через vLLM (AWQ, ctx 4096) |
| Embeddings | `intfloat/multilingual-e5-small` (384) или MOCK |
| OCR | MOCK (`provider=MOCK`) |

## Структура репозитория

| Путь | Что внутри | Связь с формой |
| ---- | ---------- | -------------- |
| [`app/infra/`](app/infra/) | compose + Helm | ≈ `/infra` |
| [`app/backend/`](app/backend/) | Agents + API | ≈ `/backend` |
| [`app/frontend/`](app/frontend/) | UI | доп. функционал |
| [`docs/`](docs/) | SETUP, capacity, load, evidence | `/docs` |
| [`architecture/`](architecture/) | ADD: C4, ADR, diagrams | ADD |
| [`tools/diagrams/`](tools/diagrams/) | генерация схем из кода | доп. функционал |
| [`tasks/`](tasks/) | video script | демо |
| [`data/`](data/) | runtime object-store (не исходники) | — |

## Архитектура из кода

Канонические схемы собираются из реализации (Structurizr, LangGraph, Pyreverse, Helm→KubeDiagrams).

```powershell
python tools/diagrams/build.py --bootstrap
python tools/diagrams/build.py --profile desktop
python tools/diagrams/build.py --profile desktop --check
```

Документация: **[docs/DIAGRAMS.md](docs/DIAGRAMS.md)** · SVG: [architecture/diagrams/images/](architecture/diagrams/images/).

## Быстрый старт

Полная инструкция: **[docs/SETUP.md](docs/SETUP.md)**.

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
```

```bash
bash app/scripts/hybrid/hybrid-up.sh
cd app/backend && .venv/Scripts/python -m pytest -q   # Windows venv
```

Demo auth: Bearer `guest` | `associate` | `manager` | `compliance`.

## Известные отклонения

1. **Видео** — единственный открытый пункт формы сдачи (сценарий готов).
2. **Пути monorepo** — `app/infra`, `app/backend` вместо корневых `/infra`, `/backend`.
3. **Observability** — Tempo вместо Jaeger; логи Ollama вместо vLLM (нет GPU).
4. **OCR = MOCK** — контракт пайплайна, не real vision.
5. **Demo-auth** — учебные Bearer-токены.
6. **Vault** — planned stub.

## Автор

**Евгений Юлов** — Platform Engineer / AI Architect (учебный case study).

GitHub: [YuesIt17/yuit-docs-ai-architect-platform](https://github.com/YuesIt17/yuit-docs-ai-architect-platform)
