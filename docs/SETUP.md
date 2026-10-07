# Настройка и запуск инфраструктуры

Два пути:

| Режим | Когда использовать | Команда |
|-------|--------------------|---------|
| **A. Без Kubernetes** (Docker Compose) | Ноутбук, быстрый демо, CI | `make demo` |
| **B. С Kubernetes** (Docker Desktop + Helm) | «Прод-like» деплой | `.\scripts\k8s-up.ps1` |

Оба пути поднимают Control Plane (API + Frontend) и Data Plane (Neo4j, Qdrant, MinIO, Postgres, Redis). LLM — отдельно (MOCK по умолчанию).

**Архитектура инфры** (сети, pods, planes, схемы): **[docs/infra/](infra/)** · Compose: [compose-dev.md](infra/compose-dev.md) · K8s: [k8s-architecture.md](infra/k8s-architecture.md).  
**Ops-команды** (curl / kubectl / Helm): **[SRE.md](SRE.md)**.

---

## Предварительные требования

### Общее

- Docker Desktop (Windows, WSL2 backend рекомендуется)
- Git
- Python 3.11+ (для локального API без compose)
- Node.js 20+ (для `npm run dev`)

### Только для Kubernetes

- [Helm 3](https://helm.sh/docs/intro/install/)
- kubectl
- (опционально legacy) [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)

Проверка:

```powershell
docker version
helm version
kubectl version --client
```

---

## A. Без Kubernetes (Docker Compose)

### A1. Полный стек (рекомендуется для демо)

```powershell
cd yuit-docs-ai-architect-platform
make demo
```

| Сервис | URL / порт |
|--------|------------|
| Frontend (UI) | http://localhost:5173 |
| API | http://localhost:8080 |
| Neo4j Browser | http://localhost:7474 (neo4j / retailpartnerx) |
| Qdrant | http://localhost:6333 |
| MinIO API / Console | http://localhost:9000 / http://localhost:9001 (minioadmin / minioadmin) |
| Jaeger | http://localhost:16686 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Postgres | localhost:5432 (kp / kp) |
| Redis | localhost:6379 |

```powershell
curl http://localhost:8080/health
make down
```

Топы сервисов / networks / profiles: [infra/compose-dev.md](infra/compose-dev.md).

### A2. Локальная разработка (API + UI на хосте, БД в Docker)

```powershell
docker compose -f infra/docker-compose.yml --profile core up -d postgres neo4j qdrant redis minio minio-init jaeger prometheus grafana
```

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:LLM_PROVIDER = "MOCK"
uvicorn app.main:app --reload --port 8080
```

```powershell
cd frontend
npm install
npm run dev
# http://localhost:5173  (proxy /api → :8080)
```

> Если на 8080 уже крутится uvicorn, а вы поднимаете `make demo`, будет конфликт портов.

### A3. Локальный LLM + observability

```powershell
make llm-ollama    # Ollama :11434, qwen2.5:0.5b
make obs           # Prometheus / Grafana / MinIO / Jaeger
make llm-vllm      # NVIDIA GPU profile
```

В UI → **LLM**: Provider `OLLAMA`, Base URL `http://localhost:11434/v1` (API на хосте) или `http://ollama:11434/v1` (API в том же compose), model `qwen2.5:0.5b`. Роль manager/compliance → Apply.

По умолчанию `LLM_PROVIDER=MOCK`, `STORE_BACKEND=live` (MinIO). Hybrid с K8s: см. [infra/k8s-architecture.md](infra/k8s-architecture.md).

### A4. Роли и ACL в UI

| Role | Clearance |
|------|-----------|
| guest | public |
| associate | public + internal |
| manager | public + internal |
| compliance | + secret |

Проверка: manager не видит secret promo (`42%`); compliance видит.

---

## B. С Kubernetes (Docker Desktop + Helm)

### B1. Инструменты

- Docker Desktop с **Enable Kubernetes**
- Helm 3, kubectl

```powershell
kubectl config use-context docker-desktop
kubectl get nodes
```

Legacy kind: `$env:KP_K8S='kind'`.

### B2. Подъём

```powershell
.\scripts\k8s-up.ps1
```

Скрипт: build `kp-api:dev` / `kp-frontend:dev` → ingress-nginx на **:8088** → Helm + [`values-desktop.yaml`](../infra/helm/knowledge-platform/values-desktop.yaml).

Hosts (admin): `127.0.0.1 kp.local`

| Что | URL |
|-----|-----|
| UI | http://kp.local:8088 |
| API health | http://kp.local:8088/api/health |

```powershell
curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health
```

Снос: `.\scripts\k8s-down.ps1`

### B3. LLM side-stack

MOCK в кластере по умолчанию. Ollama — в Compose (`make llm-ollama`); API в K8s → `http://host.docker.internal:11434/v1`.

```powershell
$env:KP_LLM = "compose-ollama"
.\scripts\k8s-up.ps1
```

In-cluster Ollama (тяжело для ноутбука): `$env:KP_LLM='ollama'; .\scripts\k8s-up.ps1`

Ноды, pods, planes, ingress: **[infra/k8s-architecture.md](infra/k8s-architecture.md)**. Команды: **[SRE.md](SRE.md)**.

---

## Переменные окружения (кратко)

См. [.env.example](../.env.example).

| Переменная | Смысл | Пример |
|------------|--------|--------|
| `LLM_PROVIDER` | стартовый provider | `MOCK` / `OLLAMA` / `VLLM` |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | `http://ollama:11434/v1` |
| `LLM_MODEL` | имя модели | `qwen2.5:7b-instruct` |
| `STORE_BACKEND` | `memory` или `live` | `memory` для MVP |

Runtime-смена без рестарта: UI **LLM** → Apply (manager/compliance).

---

## Типичные проблемы

| Симптом | Что сделать |
|---------|-------------|
| Ingress `:8088` / `:80` 404 от IIS | На Windows `:80` часто IIS. Ingress LB на **:8088**. Hosts: `127.0.0.1 kp.local` |
| `ollama pull` TLS handshake timeout | `.\scripts\ollama-pull.ps1` (DNS 8.8.8.8 + retries). Или MOCK без модели |
| Docker Desktop `pipe ... not found` / EOF | Engine упал. Не гоняйте kind+compose+ollama сразу. `wsl --shutdown`, рестарт Desktop, диск ≥32GB, RAM ≥6–8GB |
| Port 8080 already in use | Остановить локальный uvicorn или compose `api` |
| OTel errors `localhost:4317` | Нормально, если Jaeger ещё не поднят; `make demo` поднимает Jaeger |
| OLLAMA unreachable | `docker ps`, `.\scripts\ollama-pull.ps1`, проверить base URL (host vs `ollama` hostname) |
| kind/helm not found | Установить инструменты (см. B1); пока использовать путь A |
| Ingress 404 на /api | Проверить rewrite в Helm ingress и hosts `kp.local` |
| `minio/minio` / `bitnami/minio` pull denied | В compose/Helm — `bitnamilegacy/minio:2025.7.23-debian-12-r5`; при `STORE_BACKEND=memory` API пишет объекты на локальный FS |
| Neo4j CrashLoop `PORT.7687.TCP.PORT` | В chart уже `enableServiceLinks: false` + `NEO4J_server_config_strict__validation_enabled=false` |
| `jaeger ... manifest unknown` | Использовать тег `1.60.0` или `latest` (зафиксировано в compose) |

---

## Быстрый чеклист сдачи

1. `make demo` → UI открывается  
2. Chat MOCK → есть citations  
3. ACL manager vs compliance  
4. Labels upload  
5. (Опционально) `make llm-ollama` + Apply OLLAMA  
6. (Опционально) `.\scripts\k8s-up.ps1` → `http://kp.local:8088`
