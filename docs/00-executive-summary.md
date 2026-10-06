# Резюме для защиты — RetailPartnerX Knowledge Platform

**Заказчик:** RetailPartnerX — крупный FMCG-ритейлер.  
**Роль:** Platform Engineer / AI Architect — Internal Developer Platform для AI knowledge workloads.

## Проблема

Неструктурированные знания (политики, выдержки НПА, сканы этикеток) приводят к галлюцинациям и потере контекста. Чувствительные promo/margin документы не должны утекать между ролями.

## Решение

On-premise **GraphRAG Knowledge Platform**:

- **Control Plane:** AuthZ/RBAC, Input/Output Guardrails, LangGraph, ACL на retrieval
- **Data Plane:** Neo4j, Qdrant (compose + in-memory MVP), MinIO, Postgres, vLLM/Ollama/MOCK
- **Модальности:** text chat + распознавание этикеток (PDF/PNG/…)
- **Handoff:** JSON в MinIO `exports/` + outbox `label.recognized` → PIM/ERP

## Continuity

Развитие кейса из `yuit-docs-ai-architect` (hw-1…hw-10) и pointer [hw-11](../../yuit-docs-ai-architect/hw-11/): dual KB, LangGraph, security layer, vLLM sizing, sync/async, FinOps/Model Card. **Инверсия hw-4:** self-hosted LLM вместо SaaS.

## Доказательства на демо

1. `category_manager` не получает secret promo; `compliance_officer` — получает  
2. Upload этикетки → OCR extract → policy citations  
3. Jaeger/OTel + Prometheus + Neo4j Browser  

## Карта артефактов

| Раздел | Путь |
| ------ | ---- |
| Задание / критерии | [README](../README.md) |
| C4 / Deployment / Sequence / ER / Data Flow | [architecture/](architecture/) · [diagrams/](../diagrams/) |
| ADR | [adr/](adr/) |
| Демо / нагрузка | [demo-script.md](demo-script.md) · [load-report.md](load-report.md) |
| Model Card | [model-card.md](model-card.md) |

Учебный MVP: runtime GraphRAG — in-memory mirror онтологии; Neo4j/Qdrant в compose для Browser и sync.
