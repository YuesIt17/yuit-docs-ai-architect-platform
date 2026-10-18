# Compose — hybrid side-stack

**Схема:** [compose-topology.png](../../architecture/diagrams/compose-topology.png) · [compose-topology.drawio](../../architecture/diagrams/compose-topology.drawio)

Источник: [`app/infra/docker-compose.yml`](../../app/infra/docker-compose.yml), [`Makefile`](../../Makefile).  
Запуск: [SETUP.md](../SETUP.md) · ops: [SRE.md](../SRE.md).

Project: `retailpartnerx-kp`.

## Правило zero-overlap

| Слой | Где |
|------|-----|
| Platform (api, frontend, postgres, neo4j, qdrant, redis, **minio**) | **только Kubernetes** |
| LLM (**ollama**) | **только Compose** |
| Observability (prometheus, grafana, jaeger) | **только Compose** |

## Profiles

| Profile | Сервисы |
|---------|---------|
| `obs` | jaeger, prometheus, grafana |
| `llm` | ollama |

Сканеры безопасности (отдельный файл, ephemeral): [sec-ops.md](sec-ops.md) · `make sec-scan` · [`docker-compose.sec-ops.yml`](../../app/infra/docker-compose.sec-ops.yml).

| Target | Windows | macOS |
|--------|---------|-------|
| Hybrid up | `.\app\scripts\hybrid\hybrid-up.ps1` | `bash app/scripts/hybrid/hybrid-up.sh` |
| `llm` + `obs` | `docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d` | то же |
| Sec scanners | `.\app\scripts\sec\sec-scan.ps1` | `bash app/scripts/sec/sec-scan.sh` |

## Порты (Compose)

| Сервис | Порт |
|--------|------|
| ollama | **11434** |
| jaeger | **16686**, 4317/4318 |
| prometheus | **9090** |
| grafana | **3000** |

Prometheus scrape (hybrid): `host.docker.internal:30080/metrics` (API NodePort).

Grafana provisioning: `app/infra/grafana/provisioning/` → datasource Prometheus + dashboard **KP Overview** (folder Knowledge Platform).

## Hybrid flow

**Windows**

```powershell
.\app\scripts\hybrid\hybrid-up.ps1
# или: make demo
```

**macOS**

```bash
bash app/scripts/hybrid/hybrid-up.sh
# или: make demo
```

API в K8s → Ollama: `http://host.docker.internal:11434/v1`  
API → Jaeger: `http://host.docker.internal:4318` (OTLP/HTTP, Helm env).

После chat: Jaeger service `kp-api`, Grafana panels (requests / RAG p95 / tokens).

Подробности K8s: [k8s-architecture.md](k8s-architecture.md).
