# ADR-003: Graph Database

## Статус

Accepted

## Контекст

Простой векторный поиск недостаточен для критерия курса (GraphRAG). Нужна онтология корпоративных знаний RetailPartnerX: документы, чанки, сущности, темы, этикетки — и рёбра связей для multi-hop resolve до dense search.

## Критерии выбора

- Self-hosted graph + Browser для демо
- Простая онтология 4–5 типов узлов
- Cypher / визуализация для защиты
- Зеркалирование модели в in-memory MVP

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **Neo4j Community** | Browser, Cypher, зрелая экосистема | JVM footprint |
| Memgraph | Быстрый in-mem | Меньше учебного материала |
| Nebula | Scale-out | Избыточно для MVP |

## Решение

**Neo4j Community** для онтологии GraphRAG:

- Узлы: `Document`, `Chunk`, `Entity`, `Topic`, `LabelAsset`
- Рёбра: `CONTAINS`, `REFERENCES`, `ABOUT`, `AMENDS`, `HAS_ALLERGEN`, `GOVERNS`, `EXTRACTED_FROM`, `DESCRIBES_SKU`

**MVP runtime:** in-memory graph с той же моделью; compose Neo4j — для Browser-демо и sync-пайплайнов. Это закрывает требование GraphRAG без ложного заявления «live Cypher на каждый chat».

## Последствия

- (+) Явные связи снижают потерю контекста vs «мешок чанков»
- (−) Нужна дисциплина ingest/ontology; dual-write memory↔Neo4j на этапе роста

## Ссылки

- ER: [docs/architecture/er-diagram.md](../architecture/er-diagram.md)
- `backend/app/services/knowledge_store.py`, `pipelines/sync_neo4j.py`
