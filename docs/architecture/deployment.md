# Deployment — физическое размещение

**Схема (Draw.io):** [deployment.png](../../diagrams/deployment.png) · [deployment.drawio](../../diagrams/deployment.drawio)

## Назначение

Сегментация сети (DMZ / Internal Control / Data / GPU), балансировка, секреты, учёт GPU для on-prem LLM.

## Сегменты

| Сегмент | Состав |
| ------- | ------ |
| DMZ / Edge | Load Balancer → `kp-api` |
| Internal Control | Prometheus, Grafana, Jaeger, Vault (stub) |
| Data | Postgres, Neo4j, Qdrant, Redis, MinIO |
| GPU Pool | vLLM (опциональный compose profile) |

## Секреты и GPU

- **Secrets:** Vault file stub / env — никогда в образах.
- **GPU:** consumer GPU → квантование AWQ/GGUF ([ADR-001](../adr/ADR-001-llm-serving.md)). Без GPU — Ollama small / MOCK.

```mermaid
flowchart TB
  subgraph dmz [DMZ]
    LB[Load_Balancer]
    API[kp-api]
  end
  subgraph internal [Internal_Control]
    Prom[Prometheus]
    Graf[Grafana]
    Jaeger[Jaeger]
    Vault[Vault_Stub]
  end
  subgraph dataplane [Data_Segment]
    PG[(Postgres)]
    N4[(Neo4j)]
    QD[(Qdrant)]
    RD[(Redis)]
    S3[(MinIO)]
  end
  subgraph gpu [GPU_Pool]
    vLLM[vLLM]
  end
  LB --> API
  API --> PG
  API --> N4
  API --> QD
  API --> RD
  API --> S3
  API --> vLLM
  API --> Jaeger
  Prom --> API
  Graf --> Prom
  API --> Vault
```

K8s (Docker Desktop / kind): [../infra/k8s-architecture.md](../infra/k8s-architecture.md).
