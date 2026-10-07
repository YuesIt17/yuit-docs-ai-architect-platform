# Инфраструктура Knowledge Platform

Фактическая топология **дев-среды** (Docker Compose) и **Kubernetes** (Docker Desktop + Helm). Логические сегменты DMZ / Control / Data / GPU — в [architecture/deployment.md](../architecture/deployment.md).

| Путь | Когда | Документ | Схема |
|------|-------|----------|-------|
| **Compose** | Ноутбук, быстрый демо, CI | [compose-dev.md](compose-dev.md) | [compose-topology.png](../../diagrams/compose-topology.png) |
| **Kubernetes** | Prod-like деплой | [k8s-architecture.md](k8s-architecture.md) | [k8s-topology.png](../../diagrams/k8s-topology.png) |

## Запуск и ops

| Что | Где |
|-----|-----|
| How-to (команды подъёма) | [SETUP.md](../SETUP.md) |
| curl / kubectl / Helm / Compose | [SRE.md](../SRE.md) |
| Helm chart / compose файлы | [`infra/`](../../infra/) |

## Compose vs K8s (кратко)

| | Compose | Desktop K8s |
|--|---------|-------------|
| Entry | `make demo` | `.\scripts\k8s-up.ps1` |
| UI / API | `:5173` / `:8080` | `http://kp.local:8088` (ingress) |
| Data plane | Postgres, Neo4j, Qdrant, Redis, MinIO | Те же stores в namespace `kp` |
| Observability | Prometheus, Grafana, Jaeger | **Не** в Helm — `make obs` в Compose |
| LLM | `make llm-ollama` (profile `llm`) | MOCK по умолчанию; Ollama с хоста через `host.docker.internal` |
