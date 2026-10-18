# Глоссарий Knowledge Platform

Термины в контексте RetailPartnerX Knowledge Platform (KP).

### GraphRAG

Гибридный retrieval: сначала resolve сущностей и связей в графе знаний (Neo4j / in-memory mirror), затем векторный поиск по чанкам с фильтром ACL. Цель — меньше галлюцинаций и потери контекста, чем у «мешка эмбеддингов». См. [ADR-003](../architecture/adr/ADR-003-graph-db.md), [data-flow](../architecture/data-flow.md).

### Control Plane

Слой управления запросом: AuthN/RBAC, Input/Output Guardrails, LangGraph-оркестратор, политики и semantic cache. Не хранит сырые knowledge-blobs — решает, *кому* и *как* отвечать. См. [c4-container](../architecture/c4-container.md).

### Data Plane

Хранилища и inference: Neo4j, Qdrant, MinIO, Postgres, Redis, LLM Serving (Ollama/MOCK). Изолирован от edge; доступ идёт через Control Plane. В hybrid-стенде stores живут в K8s, Ollama/obs — в Compose.

### Air-gapped / closed loop

Режим без egress к SaaS LLM (OpenAI/Anthropic и аналоги). Ответы только через self-hosted Ollama или MOCK. См. [ADR-001](../architecture/adr/ADR-001-llm-serving.md).

### ACL на чанке

Метаданные `classification` + `allowed_roles` на чанке/узле; фильтр применяется **до** передачи контекста в LLM, чтобы User B не увидел секретный документ. Демо: manager vs compliance. См. [ADR-005](../architecture/adr/ADR-005-security.md).

### LabelAsset

Мультимодальный артефакт этикетки: исходный файл + URI в object store (`raw` / `recognized` / `export`). Пайплайн: upload → OCR/vision extract → citations политик → JSON для PIM. См. [ADR-007](../architecture/adr/ADR-007-multimodal-labels.md).

### Paved Road

«Золотой путь» поднятия демо: hybrid Compose (Ollama + observability) + K8s (api/frontend/stores), без дублей сервисов. Точка входа: `make demo` / [`docs/SETUP.md`](SETUP.md).

### Soft degrade

При timeout или недоступности LLM API отвечает с fallback (MOCK) и флагом `degraded=true`, вместо жёсткого 5xx. Сохраняет демо и UX при сбое inference. См. [ADR-008](../architecture/adr/ADR-008-sync-async-cache.md).

### Semantic Cache

Кэш готовых ответов **после** Output Guard; ключ учитывает роль и версию индекса (`index_version`). Инвалидация при смене политик/индекса. См. [ADR-008](../architecture/adr/ADR-008-sync-async-cache.md).

### LLM Serving

Слой выдачи токенов: Ollama (OpenAI-compatible API) или MOCK для тестов/демо без модели. Выбор и URL задаются runtime (`LLM_PROVIDER`, base URL). См. [ADR-001](../architecture/adr/ADR-001-llm-serving.md).

### Outbox

Таблица/поток событий (например `label.recognized`) для надёжной передачи результата в PIM/ERP без прямой синхронной связи. См. [ADR-009](../architecture/adr/ADR-009-object-store.md), [data-flow](../architecture/data-flow.md).

### Trust boundary

Граница доверия BFF ↔ Knowledge Platform: снаружи только OpenAPI (и SSE chat); внутренние stores и LLM не торчат в DMZ. См. [c4-context](../architecture/c4-context.md), [deployment](../architecture/deployment.md).
