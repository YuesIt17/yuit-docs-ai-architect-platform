# Настройка и запуск инфраструктуры

| Режим | Когда | Команда (PowerShell) |
|-------|-------|----------------------|
| **Hybrid (рекомендуется)** | Desktop / защита — **без дублей** | `.\scripts\hybrid-up.ps1` |
| **Standalone Compose** | Без K8s / CI | см. ниже |
| **Только K8s** | MOCK, без Ollama/obs | `.\scripts\k8s-up.ps1` |

> На Windows **`make` не нужен** — в SETUP везде PowerShell. (`make demo` = обёртка над `hybrid-up.ps1`, если установлен GNU Make / chocolatey `make`.)

**Hybrid zero-overlap:** K8s = api/frontend/stores/**minio**; Compose = **ollama** + prometheus/grafana/jaeger.

Архитектура: **[docs/infra/](infra/)** · ops: **[SRE.md](SRE.md)**.

---

## Предварительные требования

- Docker Desktop (WSL2), Git, Helm 3, kubectl
- Python 3.11+ / Node 20+ — только для локальной разработки API/UI на хосте

```powershell
docker version
helm version
kubectl version --client
kubectl config use-context docker-desktop
```

Hosts (admin): `127.0.0.1 kp.local`

---

## A. Hybrid (рекомендуется)

```powershell
cd yuit-docs-ai-architect-platform
.\scripts\hybrid-up.ps1
# side-stack (ollama + obs) + k8s-up с KP_LLM=compose-ollama
```

| Что | URL |
|-----|-----|
| UI | http://kp.local:8088 |
| API health | http://kp.local:8088/api/health |
| Ollama | http://127.0.0.1:11434/v1/models |
| Jaeger | http://127.0.0.1:16686 |
| Prometheus | http://127.0.0.1:9090 |
| Grafana | http://127.0.0.1:3000 (admin) |
| MinIO | `kubectl -n kp port-forward svc/minio 9000:9000 9001:9001` |
| Neo4j (in-cluster) | `kubectl -n kp port-forward svc/neo4j 7474:7474 7687:7687` |

Side-stack отдельно:

```powershell
docker compose -f infra/docker-compose.yml --profile llm --profile obs up -d
.\scripts\ollama-pull.ps1 -Model qwen2.5:0.5b
```

LLM в UI: Provider `OLLAMA`, Base URL `http://host.docker.internal:11434/v1`, model `qwen2.5:0.5b` (preset по умолчанию).

Снос:

```powershell
.\scripts\k8s-down.ps1
docker compose -f infra/docker-compose.yml --profile obs --profile llm --profile llm-gpu down -v
```

---

## B. Standalone Compose (без K8s)

**Не** сочетать с `k8s-up` — конфликт портов/stores.

```powershell
docker compose -f infra/docker-compose.standalone.yml up -d --build
# UI http://localhost:5173  API http://localhost:8080
```

Файл: [`infra/docker-compose.standalone.yml`](../infra/docker-compose.standalone.yml).  
`STORE_BACKEND=memory` (MinIO нет). Ollama: side-stack `--profile llm` или MOCK.

---

## C. Локальная разработка API/UI на хосте

Нужны stores — либо K8s port-forward, либо `demo-standalone` без api/frontend контейнеров.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:LLM_PROVIDER = "MOCK"
$env:STORE_BACKEND = "memory"
uvicorn app.main:app --reload --port 8080
```

```powershell
cd frontend
npm install
npm run dev
```

---

## Роли и ACL

| Role | Clearance |
|------|-----------|
| guest | public |
| associate / manager | public + internal |
| compliance | + secret |

manager не видит secret promo (`42%`); compliance видит.

---

## Переменные

См. [.env.example](../.env.example).

| Переменная | Смысл | Hybrid |
|------------|-------|--------|
| `LLM_PROVIDER` | MOCK / OLLAMA / VLLM | overlay / UI Apply |
| `OPENAI_BASE_URL` | endpoint из **пода API** | `http://host.docker.internal:11434/v1` |
| `STORE_BACKEND` | memory / live | `live` в K8s desktop |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | traces | `http://host.docker.internal:4317` |

---

## Типичные проблемы

| Симптом | Что сделать |
|---------|-------------|
| OLLAMA unreachable | Base URL `host.docker.internal`, не `localhost` из пода |
| Port clash / два postgres | Не гонять `demo-standalone` + K8s |
| Ingress `:8088` 404 IIS | Hosts `kp.local`, LB на 8088 |
| `ollama pull` TLS timeout | `.\scripts\ollama-pull.ps1` |
| MinIO 9000 на хосте пусто | MinIO только в K8s → port-forward |

---

## Чеклист сдачи

1. `.\scripts\hybrid-up.ps1` → http://kp.local:8088
2. Chat MOCK/OLLAMA → citations
3. ACL manager vs compliance
4. Labels upload (MinIO in-cluster)
5. Jaeger / Prometheus / Grafana с Compose
6. (Опционально) Graph Neo4j port-forward
