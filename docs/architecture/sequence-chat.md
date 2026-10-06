# Sequence — сложный chat-запрос

**Схема (Draw.io):** [sequence-chat.png](../../diagrams/sequence-chat.png) · [sequence-chat.drawio](../../diagrams/sequence-chat.drawio)

## Назначение

Флоу: User → Guardrails → (cache) → Agent Loop (graph resolve → vector + ACL → LLM) → Output Guard → Response. Соответствует требованию курса Sequence Diagram.

## ACL-deny (критичный сценарий)

Если роль `category_manager` запрашивает секретный promo: vector/graph retrieve **не возвращает** secret-чанки; Output Guard дополнительно блокирует утечку маркеров вроде `42%`. Роль `compliance_officer` получает citations по secret.

```mermaid
sequenceDiagram
  actor U as CategoryManager
  participant GW as API
  participant IG as InputGuard
  participant Cache as SemanticCache
  participant Orch as LangGraph
  participant G as Neo4jGraph
  participant V as VectorIndex
  participant LLM as LLMServing
  participant OG as OutputGuard
  participant A as Audit

  U->>GW: POST /v1/chat Bearer manager
  GW->>IG: sanitize + injection check
  IG->>Cache: lookup
  alt cache hit
    Cache-->>GW: answer
  else miss
    GW->>Orch: invoke graph
    Orch->>G: entity/topic resolve
    Orch->>V: dense search + ACL filter
    Orch->>LLM: synthesize with context
    LLM-->>Orch: draft
    Orch->>OG: citations + ACL check
    OG->>A: decision row
    OG-->>GW: answer + citations
  end
  GW-->>U: SSE final / JSON
```
