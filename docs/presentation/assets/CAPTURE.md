# Скрины для defense-deck

Файлы в этой папке подключаются из [`../defense-deck.html`](../defense-deck.html).

## Уже есть

| Файл | Содержание |
|------|------------|
| `ui-chat.png` | Chat (промпт) |
| `ui-labels.png` | Labels OCR=MOCK |
| `ui-llm.png` | LLM Settings OLLAMA |
| `ui-graph.png` | Graph seed=gluten |
| `ui-ops.png` | Ops health live |
| `ui-acl-manager-deny.png` | manager → `deny_retrieval` |
| `ui-acl-compliance-allow.png` | compliance → secret allow |
| `grafana-kp-overview-1.png` | KP Overview (UP, req, cache, RAG) |
| `grafana-kp-overview-2.png` | KP Overview (tokens, totals) |
| `grafana-acl-denies.png` | ACL denies / min > 0 |
| `grafana-tempo.png` | Grafana Explore → Tempo → trace detail + spans `kp-api` |

## Опционально доснять

| Файл | Как |
|------|-----|
| `ui-chat-allergen-answer.png` | Chat → Allergen prompt → Ask → ответ + citations |
| `grafana-loki.png` | Explore → Loki |
| `neo4j-browser.png` | http://127.0.0.1:30474 + Cypher из `app/scripts/demo_graph.cypher` |

После добавления PNG обнови `src` на слайдах в `defense-deck.html`.
