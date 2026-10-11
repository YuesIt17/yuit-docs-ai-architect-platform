# Compose — hybrid side-stack

**Схема:** [compose-topology.png](../../diagrams/compose-topology.png) · [compose-topology.drawio](../../diagrams/compose-topology.drawio)

Источник: [`infra/docker-compose.yml`](../../infra/docker-compose.yml), [`Makefile`](../../Makefile).  
Запуск: [SETUP.md](../SETUP.md) · ops: [SRE.md](../SRE.md).

Project: `retailpartnerx-kp`.

## Правило zero-overlap

| Слой | Где |
|------|-----|
| Platform (api, frontend, postgres, neo4j, qdrant, redis, **minio**) | **только Kubernetes** |
| LLM (**ollama**) | **только Compose** |
| Observability (prometheus, grafana, jaeger) | **только Compose** |

Не поднимать standalone Compose вместе с K8s.

## Profiles

| Profile | Сервисы |
|---------|---------|
| `obs` | jaeger, prometheus, grafana |
| `llm` | ollama |

| Target | Действие |
|--------|----------|
| `.\scripts\hybrid-up.ps1` | side-stack + K8s + OLLAMA overlay |
| `llm` + `obs` profiles | ollama + prometheus/grafana/jaeger |
| `docker-compose.standalone.yml` | полный стек **без** K8s |

## Порты (Compose)

| Сервис | Порт |
|--------|------|
| ollama | **11434** |
| jaeger | **16686**, 4317/4318 |
| prometheus | **9090** |
| grafana | **3000** |

Prometheus scrape (hybrid): `host.docker.internal:30080/metrics` (API NodePort).

Grafana provisioning: `infra/grafana/provisioning/` → datasource Prometheus + dashboard **KP Overview** (folder Knowledge Platform).

## Hybrid flow

```powershell
.\scripts\hybrid-up.ps1
```

API в K8s → Ollama: `http://host.docker.internal:11434/v1`  
API → Jaeger: `http://host.docker.internal:4318` (OTLP/HTTP, Helm env).

После chat: Jaeger service `kp-api`, Grafana panels (requests / RAG p95 / tokens).

Подробности K8s: [k8s-architecture.md](k8s-architecture.md).
