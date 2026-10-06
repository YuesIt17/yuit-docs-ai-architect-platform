# ADR-002: Vector Database

## Статус

Accepted

## Контекст

Нужен self-hosted векторный индекс для RAG по политикам, чанкам этикеток и документам с **payload-фильтрацией ACL** (`classification`, `allowed_roles`) до передачи контекста в LLM.

## Критерии выбора

- Self-hosted, без облачного managed DB
- Фильтры по payload на query-time
- Простой ops для MVP / compose
- Совместимость с CI без Docker (in-process fallback)

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **Qdrant** | Простой compose, сильный payload filter | Меньше «enterprise» фич, чем Milvus |
| Milvus | Масштаб, GPU index | Тяжелее ops |
| Weaviate | Модули, hybrid | Сложнее схема для MVP |
| pgvector | Одна Postgres | Слабее для dense ANN @ scale |

## Решение

**Qdrant** self-hosted (compose). MVP также держит **in-process** векторный индекс с теми же ACL-полями для CI без Docker. Compose Qdrant синхронизируется пайплайнами для демо; runtime chat в MVP читает in-memory mirror (честный учебный компромисс).

## Последствия

- (+) Быстрый путь ACL на retrieval; лёгкий demo stack
- (−) Нужна дисциплина sync schema payload ↔ graph; live Qdrant на каждый chat — этап после MVP

## Ссылки

- `backend/app/services/knowledge_store.py`
- Compose: `infra/docker-compose.yml`
