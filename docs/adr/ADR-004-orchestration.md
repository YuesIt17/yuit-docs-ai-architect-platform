# ADR-004: Orchestration (LangGraph)

## Статус

Accepted

## Контекст

Курс запрещает линейные цепочки («скрипт из вызовов LLM»). Нужен stateful агент: guard → route → retrieve/label → synthesize → output guard, с возможностью ветвлений и tool nodes (ReAct-стиль).

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

`guard_input → route → (graph_retrieve → vector_retrieve | label_recognize → policy_check) → synthesize → guard_output`

Наследует SRP из hw-3: policy_check как tool узла (аналог Policy Analyst).

## Последствия

- (+) Соответствие критерию «не линейный скрипт»; явные точки ACL/guard
- (−) Сложнее отладка графа; checkpoint persistence — опционально после MVP

## Ссылки

- `backend/app/agent/graph.py`, `backend/app/agent/state.py`
- Sequence: [sequence-chat.md](../architecture/sequence-chat.md)
