# C4 Level 3 — Agent Components

```mermaid
flowchart LR
  GI[guard_input] --> RT[route]
  RT -->|chat| GR[graph_retrieve]
  GR --> VR[vector_retrieve]
  VR --> SYN[synthesize]
  RT -->|label| LR[label_recognize]
  LR --> PC[policy_check]
  PC --> SYN
  SYN --> GO[guard_output]
  RT -->|blocked| GO
```

| Component | Responsibility |
|-----------|----------------|
| Memory (session/audit) | Postgres + in-memory audit trail |
| Planner / route | chat vs label vs blocked |
| Tools | graph_retrieve, vector_retrieve, label_recognize, policy_check |
| Synthesizer | LLM via OpenAI-compatible client |
| Guardrails | PII, injection, ACL leak check |