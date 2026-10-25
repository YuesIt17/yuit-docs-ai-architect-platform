# C4 L4 — Code view (compact)

Уровень кода для ключевых deployable units (не полный class diagram).

## API (`app/backend/kp`)

```
main.create_app
  └─ api.router
       ├─ api.chat → application.chat.ChatService
       │                ├─ security.guardrails.input_guard
       │                ├─ infrastructure.cache (re-auth via can_access)
       │                └─ agent.graph.KnowledgeAgent
       │                     ├─ graph_retrieve → store.graph_resolve_doc_ids
       │                     ├─ vector_retrieve → store.hybrid_retrieve
       │                     ├─ synthesize → infrastructure.llm.LLMClient
       │                     └─ guard_output
       ├─ api.vision → application.vision (OCR MOCK) → object_store + store
       └─ api.health (/health liveness, /ready readiness)
```

## Store facade

```
HybridKnowledgeStore
  ├─ MemoryKnowledgeStore (always)
  ├─ Neo4jGraphRepository (live: ABOUT / HAS_ALLERGEN / GOVERNS)
  └─ QdrantVectorRepository (live: ACL query_filter + post-check)
```

## Security

```
security.rbac.can_access / resolve_principal(DEMO_AUTH_ENABLED)
security.guardrails.input_guard / output_guard / vision_input_guard
```

См. также L3: [c4-component.md](c4-component.md).
