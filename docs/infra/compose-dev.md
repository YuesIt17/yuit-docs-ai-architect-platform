# Compose — hybrid side-stack

**Схема:** [compose-topology.png](../../diagrams/compose-topology.png) · [compose-topology.drawio](../../diagrams/compose-topology.drawio)

Источник: [`infra/docker-compose.yml`](../../infra/docker-compose.yml), [`Makefile`](../../Makefile).  
Запуск: [SETUP.md](../SETUP.md) · ops: [SRE.md](../SRE.md).

Project: `retailpartnerx-kp`.

## Правило zero-overlap

| Слой | Где |
|------|-----|
| Platform (api, frontend, postgres, neo4j, qdrant, redis, **minio**) | **только Kubernetes** |
| LLM (ollama / vllm) | **только Compose** |
| Observability (prometheus, grafana, jaeger) | **только Compose** |

Не поднимать `make demo-standalone` вместе с K8s.

## Profiles

| Profile | Сервисы |
|---------|---------|
| `obs` | jaeger, prometheus, grafana |
| `llm` | ollama |
| `llm-gpu` | vllm |

| Target | Действие |
|--------|----------|
| `make demo` / `scripts/hybrid-up.ps1` | side-stack + K8s + OLLAMA overlay |
| `make side` | `llm-ollama` + `obs` |
| `make llm-ollama` | ollama + pull `qwen2.5:0.5b` |
| `make obs` | prometheus, grafana, jaeger |
| `make demo-standalone` | полный стек **без** K8s ([docker-compose.standalone.yml](../../infra/docker-compose.standalone.yml)) |
| `make down` | down side + standalone |

## Порты (Compose)

| Сервис | Порт |
|--------|------|
| ollama | **11434** |
| jaeger | **16686**, 4317/4318 |
| prometheus | **9090** |
| grafana | **3000** |
| vllm (opt) | **8000** |

Prometheus scrape (hybrid): `host.docker.internal:8088/api/metrics` + `Host: kp.local`.

## Hybrid flow

```powershell
make demo
# или:
make side
$env:KP_LLM = "compose-ollama"
.\scripts\k8s-up.ps1
```

API в K8s → Ollama: `http://host.docker.internal:11434/v1`  
API → Jaeger: `http://host.docker.internal:4317` (Helm env).

Подробности K8s: [k8s-architecture.md](k8s-architecture.md).
