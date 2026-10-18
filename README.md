# Итоговый проект — RetailPartnerX Knowledge Platform

**Защищённая платформа мультимодального анализа корпоративных знаний (GraphRAG)**

> **Сокращения:** [Глоссарий](docs/Glossary.md) · **ADD:** [architecture/](architecture/) · **Ops:** [docs/](docs/) · **Setup:** [docs/SETUP.md](docs/SETUP.md) · **Runbook:** [docs/SRE.md](docs/SRE.md) · **DevSecOps:** [docs/infra/sec-ops.md](docs/infra/sec-ops.md)

## Цель

Спроектировать и реализовать **MVP производственного конвейера (End-to-End Pipeline)** для извлечения знаний из неструктурированных данных (сканы этикеток, PDF, политики) в **закрытом контуре** (On-premise / Air-gapped), без внешних API OpenAI/Anthropic.

Роль: **Platform Engineer & AI Architect**. Снижение «галлюцинаций» и потери контекста через **GraphRAG** (нейро-символический подход) и **Security-by-Design** (разграничение прав на уровне чанков / узлов графа). Кейс демонстрирует готовность к внедрению AI в enterprise-ритейле РФ (паттерны применимы к банковскому / промышленному контуру).

## Структура репозитория

| Путь | Что внутри |
| ---- | ---------- |
| [`app/`](app/) | Runnable-платформа: `backend/`, `frontend/`, `infra/` (Compose/Helm), `datasets/`, `scripts/`, `evals/` |
| [`architecture/`](architecture/) | ADD: C4 / flows / ER / sequences, ADR, [`diagrams/`](architecture/diagrams/) (drawio+png) |
| [`docs/`](docs/) | Онбординг и ops: SETUP, SRE, [`infra/`](docs/infra/) (how-to + DevSec), demo, glossary, model-card |
| [`data/`](data/) | Локальный runtime/state (object-store и т.п.), не исходники |
| Корень | `Makefile`, `.env.example` — точки входа |

**Куда идти**

- Защита / ADD → [`architecture/`](architecture/)
- Запуск стенда → [`docs/SETUP.md`](docs/SETUP.md)
- Инфра / сканеры → [`docs/infra/`](docs/infra/)
- Код и оркестрация → [`app/`](app/)

## Контекст и преемственность

Единый кейс **RetailPartnerX** (FMCG-ритейлер). Этот репозиторий — отдельный итоговый MVP; ниже — преемственность с ДЗ курса (hw-1…hw-10).

### Домашние задания (курс)

| ДЗ | Артефакт | Связь с проектом |
| -- | -------- | ---------------- |
| [hw-1](../yuit-docs-ai-architect/hw-1/) | Риски, 152-ФЗ, roadmap | Контур безопасности и residency |
| [hw-2](../yuit-docs-ai-architect/hw-2/) | C4, Sequence, API | Паттерн границ BFF ↔ AI Service |
| [hw-3](../yuit-docs-ai-architect/hw-3/) | Multi-agent + LangGraph | SRP агентов → оркестратор Knowledge Platform |
| [hw-4](../yuit-docs-ai-architect/hw-4/) | ADR SaaS LLM | **Инверсия:** self-hosted Ollama для closed loop |
| [hw-5](../yuit-docs-ai-architect/hw-5/) | Data pipeline | Ingest → chunk → embed → index |
| [hw-6](../yuit-docs-ai-architect/hw-6/) | Guardrails, eval, obs | Input/Output guards + OTel/Prometheus |
| [hw-7](../yuit-docs-ai-architect/hw-7/) | Inference sizing | GPU / квантование AWQ/GGUF |
| [hw-8](../yuit-docs-ai-architect/hw-8/) | CI/CD + K8s | Helm / kind deployment |
| [hw-9](../yuit-docs-ai-architect/hw-9/) | High-load, cache | Semantic cache, sync/async |
| [hw-10](../yuit-docs-ai-architect/hw-10/) | Model Card / FinOps | [docs/model-card.md](docs/model-card.md) |

### Финальный проект

**Задача:** для RetailPartnerX закрыть контур **корпоративной базы знаний** (политики, НПА-выдержки, этикетки, секретные promo) с GraphRAG, ACL и on-prem LLM.

Тема курса сохранена; формулировки «банк / пром» адаптированы под RetailPartnerX (FMCG, policies / labels / promo, 152-ФЗ).

## Шаги выполнения (артефакты решения)

| Шаг | Артефакт |
| --- | -------- |
| 1. Architecture & Design (C4 L1–L3, Deployment, Sequence, ER, Data Flow) | [architecture/](architecture/) · [diagrams/](architecture/diagrams/) |
| 1b. Infra topology (Compose / K8s) | [docs/infra/](docs/infra/) · [compose-topology](architecture/diagrams/compose-topology.png) · [k8s-topology](architecture/diagrams/k8s-topology.png) |
| 2. ADR со trade-off (LLM, Vector, Graph, Orchestration, Security, Obs, …) | [architecture/adr/](architecture/adr/) |
| 3. MVP: GraphRAG + LangGraph + Guardrails + multimodal labels | [app/backend/](app/backend/) · [app/frontend/](app/frontend/) |
| 4. Infra: Compose + Helm (Data Plane + Control Plane) | [app/infra/](app/infra/) |
| 5. Демо-скрипт 5–7 мин | [docs/demo-script.md](docs/demo-script.md) |
| 6. Нагрузочный отчёт | [docs/load-report.md](docs/load-report.md) |

## Формат сдачи

| Артефакт | Путь |
| -------- | ---- |
| Monorepo `app/` + `architecture/` + `docs/` | корень репозитория |
| Архитектурная документация (ADD) | [architecture/](architecture/) |
| Диаграммы Draw.io + PNG | [architecture/diagrams/](architecture/diagrams/) |
| Видео-демо (Deep Dive) | запись по [demo-script](docs/demo-script.md) (вручную) |
| Нагрузочный отчёт | [docs/load-report.md](docs/load-report.md) |

GitHub: [YuesIt17/yuit-docs-ai-architect-platform](https://github.com/YuesIt17/yuit-docs-ai-architect-platform)

## Критерии самопроверки

| Критерий | Как закрыто |
| -------- | ----------- |
| Нет облачных API (OpenAI/Anthropic) | [ADR-001](architecture/adr/ADR-001-llm-serving.md); runtime MOCK / Ollama |
| Есть Deployment и Data Flow | [deployment](architecture/deployment.md) · [data-flow](architecture/data-flow.md) · [docs/infra/](docs/infra/) · [diagrams/](architecture/diagrams/) |
| GraphRAG (не только векторный поиск) | [ADR-003](architecture/adr/ADR-003-graph-db.md) · `app/backend/app/services/knowledge_store.py` · `app/backend/app/agent/graph.py` |
| ACL: User B не видит секретный документ | [ADR-005](architecture/adr/ADR-005-security.md) · demo: manager vs compliance |
| Control Plane / Data Plane | [c4-container](architecture/c4-container.md) |
| LangGraph (state machine), не линейный скрипт | [ADR-004](architecture/adr/ADR-004-orchestration.md) · `app/backend/app/agent/graph.py` |
| Observability | [ADR-006](architecture/adr/ADR-006-observability.md) · Jaeger / Prometheus / Grafana |
| Желательно: streaming | SSE в chat API (см. sequence) |
| Желательно: тесты | `cd app/backend; pytest -q` |

Статус «Принято», если критичные критерии выполнены с evidence выше.

## Быстрый старт

Полная инструкция: **[docs/SETUP.md](docs/SETUP.md)**. Инфра: **[docs/infra/](docs/infra/)**. Runbook: **[docs/SRE.md](docs/SRE.md)**. Аудит K8s / сканеры: **[docs/infra/sec-ops.md](docs/infra/sec-ops.md)** (`make sec-scan`).

**Windows**

```powershell
.\app\scripts\hybrid\hybrid-up.ps1   # hybrid: Compose (ollama+obs) + K8s
```

**macOS**

```bash
bash app/scripts/hybrid/hybrid-up.sh   # или: make demo
```

| Сервис | Где | URL / порт |
|--------|-----|------------|
| UI / API | K8s | http://kp.local:8088 |
| MinIO / stores | K8s | port-forward при необходимости |
| Ollama | Compose | :11434 |
| Jaeger / Prom / Grafana | Compose | :16686 / :9090 / :3000 |

Демо-токены (Role switcher): `guest` | `associate` | `manager` | `compliance`

```bash
cd app/backend && pytest -q
```

## Автор

**Евгений Юлов** — Platform Engineer / AI Architect (учебный case study).
