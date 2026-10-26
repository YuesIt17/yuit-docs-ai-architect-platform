# Резюме для защиты — RetailPartnerX Knowledge Platform

**Заказчик:** RetailPartnerX — крупный FMCG-ритейлер.  
**Роль:** Platform Engineer / AI Architect — Internal Developer Platform для AI knowledge workloads.

## Проблема

Неструктурированные знания (политики, выдержки НПА, сканы этикеток) приводят к галлюцинациям и потере контекста. Чувствительные promo/margin документы не должны утекать между ролями.

## Решение

On-premise **GraphRAG Knowledge Platform**:

- **Control Plane:** AuthZ/RBAC, Input/Output Guardrails, LangGraph, ACL на retrieval
- **Data Plane:** Neo4j, Qdrant (compose + in-memory MVP), MinIO, Postgres, Ollama/MOCK
- **Модальности:** text chat + распознавание этикеток (PDF/PNG/…)
- **Handoff:** JSON в MinIO `exports/` + outbox `label.recognized` → PIM/ERP

## Преемственность

Развитие кейса из `yuit-docs-ai-architect` (hw-1…hw-10) и pointer [hw-11](../../yuit-docs-ai-architect/hw-11/): dual KB, LangGraph, security layer, inference sizing, sync/async, FinOps/Model Card. **Инверсия hw-4:** self-hosted Ollama вместо SaaS.

## Доказательства на демо

1. `category_manager` не получает secret promo; `compliance_officer` — получает  
2. Upload этикетки → OCR extract → policy citations  
3. Grafana LGTM (Tempo/Loki/Prom) + OTel + Neo4j Browser  

## Карта артефактов

| Раздел | Путь |
| ------ | ---- |
| Задание / критерии | [README](../README.md) |
| C4 / Deployment / Sequence / ER / Data Flow | [architecture/](../architecture/) · [diagrams SVG](../architecture/diagrams/images/) · [DIAGRAMS.md](DIAGRAMS.md) |
| Capacity Planning (VRAM / CPU / RAM) | [capacity-planning.md](capacity-planning.md) |
| ADR | [adr/](../architecture/adr/) |
| Демо / нагрузка | [AI_PLATFORM_VIDEO_SCRIPT](../tasks/AI_PLATFORM_VIDEO_SCRIPT.md) · [load-report.md](load-report.md) · [evidence/](evidence/) |
| Model Card | [model-card.md](model-card.md) |

Учебный MVP: runtime GraphRAG — in-memory mirror онтологии; Neo4j/Qdrant в compose для Browser и sync.
