# Инфраструктура Knowledge Platform

| Путь | Когда | Документ | Схема |
|------|-------|----------|-------|
| **Hybrid (рекомендуется)** | Desktop демо / защита | [compose-dev.md](compose-dev.md) + [k8s-architecture.md](k8s-architecture.md) | [k8s-topology.png](../../diagrams/k8s-topology.png) |
| **Standalone Compose** | Без K8s / CI | [docker-compose.standalone.yml](../../infra/docker-compose.standalone.yml) | [compose-topology.png](../../diagrams/compose-topology.png) |

## Zero-overlap (hybrid)

| Kubernetes `kp` | Compose `retailpartnerx-kp` |
|-----------------|-----------------------------|
| api, frontend | — |
| postgres, neo4j, qdrant, redis, **minio** | — |
| — | **ollama** (`make llm-ollama`) |
| — | prometheus, grafana, jaeger (`make obs`) |

```powershell
make demo
# = scripts/hybrid-up.ps1 → side-stack + k8s-up (KP_LLM=compose-ollama)
```

## Запуск и ops

| Что | Где |
|-----|-----|
| How-to | [SETUP.md](../SETUP.md) |
| curl / kubectl / Helm | [SRE.md](../SRE.md) |
| Chart / compose | [`infra/`](../../infra/) |

Логические DMZ / Control / Data / GPU: [architecture/deployment.md](../architecture/deployment.md).
