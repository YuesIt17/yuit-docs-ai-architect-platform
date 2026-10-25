# ADR-004: Orchestration (LangGraph)

## Статус

Accepted

## Контекст

Курс запрещает линейные цепочки («скрипт из вызовов LLM»). Нужен stateful агент: guard → route → retrieve/label → synthesize → output guard, с ветвлениями. Это **фиксированная state machine**, а не автономный ReAct / Plan-and-Solve.

## Критерии выбора

- Явная state machine / граф состояний
- Ветвление chat / label / blocked
- Наблюдаемость шагов (tracing)
- Continuity с hw-3 (Supervisor / Policy Analyst)

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **LangGraph** | Stateful graph, checkpointing ecosystem | Кривая обучения |
| LlamaIndex Workflows | Удобен для RAG | Меньше «agent loop» в кейсе |
| Linear LangChain LCEL | Просто | **Не принимается** критерием курса |
| CrewAI multi-agent | Роли из коробки | Тяжелее для MVP ACL path |

## Решение

**LangGraph** state machine:

`guard_input → route → (graph_retrieve → vector_retrieve [→ optional refine] | label_recognize → policy_check) → synthesize → guard_output`

`graph_retrieve` передаёт `graph_doc_ids` в `vector_retrieve` (без повторного «театрального» resolve). Опциональный bounded refine (`RETRIEVAL_REFINE_MAX`). Checkpoint / session memory — planned.

## Последствия

- (+) Соответствие критерию «не линейный скрипт»; явные точки ACL/guard
- (−) Сложнее отладка графа; checkpoint persistence — опционально после MVP

## Ссылки

- `app/backend/kp/agent/graph.py`, `app/backend/kp/agent/state.py`
- Sequence: [sequence-chat.md](../docs/sequence-chat.md)
