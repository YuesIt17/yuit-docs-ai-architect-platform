# Настройка и запуск инфраструктуры

Два пути:

| Режим | Когда использовать | Команда |
|-------|--------------------|---------|
| **A. Без Kubernetes** (Docker Compose) | Ноутбук, быстрый демо, CI | `make demo` |
| **B. С Kubernetes** (Docker Desktop + Helm) | «Прод-like» деплой | `.\scripts\k8s-up.ps1` |

Оба пути поднимают Control Plane (API + Frontend) и Data Plane (Neo4j, Qdrant, MinIO, Postgres, Redis). LLM — отдельно (MOCK по умолчанию).

---

## Предварительные требования

### Общее

- Docker Desktop (Windows, WSL2 backend рекомендуется)
- Git
- Python 3.11+ (для локального API без compose)
- Node.js 20+ (для `npm run dev`)

### Только для Kubernetes

- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [Helm 3](https://helm.sh/docs/intro/install/)
- kubectl

Проверка:

```powershell
docker version
kind version
helm version
kubectl version --client
```

---

## A. Без Kubernetes (Docker Compose)

### A1. Полный стек (рекомендуется для демо)

Из корня репозитория:

```powershell
cd yuit-docs-ai-architect-platform
make demo
# эквивалент:
# docker compose -f infra/docker-compose.yml --profile demo up -d --build
```

Поднимается:

| Сервис | URL / порт |
|--------|------------|
| Frontend (UI) | http://localhost:5173 |
| API | http://localhost:8080 |
| Neo4j Browser | http://localhost:7474 (neo4j / retailpartnerx) |
| Qdrant | http://localhost:6333 |
| MinIO API / Console | http://localhost:9000 / http://localhost:9001 (minioadmin / minioadmin); image `bitnamilegacy/minio` (`minio/minio` often blocked; `bitnami/minio` is paid-only) |
| Jaeger | http://localhost:16686 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Postgres | localhost:5432 (kp / kp) |
| Redis | localhost:6379 |

Проверка:

```powershell
curl http://localhost:8080/health
# UI: http://localhost:5173
```

Остановка:

```powershell
make down
```

### A2. Локальная разработка (API + UI на хосте, БД в Docker)

1. Поднять только data plane:

```powershell
docker compose -f infra/docker-compose.yml --profile core up -d postgres neo4j qdrant redis minio minio-init jaeger prometheus grafana
```

2. API на хосте (порт 8080 должен быть свободен):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
# при необходимости: pip install -e ".[dev]"
$env:LLM_PROVIDER = "MOCK"
uvicorn app.main:app --reload --port 8080
```

3. Frontend:

```powershell
cd frontend
npm install
npm run dev
# http://localhost:5173  (proxy /api → :8080)
```

> Если на 8080 уже крутится uvicorn, а вы поднимаете `make demo`, будет конфликт портов. Остановите локальный API или уберите сервис `api` из compose.

### A3. Локальный LLM (Ollama / vLLM)

По умолчанию `LLM_PROVIDER=MOCK` — модели не качаются.

**Ollama (CPU / ноутбук):**

```powershell
make llm-ollama
# поднимает ollama (:11434) + api + frontend
```

Скачать модель (с ретраями / DNS — чинит TLS timeout к registry.ollama.ai):

```powershell
.\scripts\ollama-pull.ps1
# или явно:
.\scripts\ollama-pull.ps1 -Model qwen2.5:1.5b-instruct
.\scripts\ollama-pull.ps1 -Model qwen2.5:7b-instruct
```

Вручную:

```powershell
docker exec -it (docker ps -qf "name=ollama") ollama pull qwen2.5:1.5b-instruct
```

В UI → **LLM**:

| Поле | Значение |
|------|----------|
| Provider | `OLLAMA` |
| Base URL (API в Docker) | `http://ollama:11434/v1` |
| Base URL (API на хосте) | `http://localhost:11434/v1` |
| Model | `qwen2.5:1.5b-instruct` или `qwen2.5:7b-instruct` |

**Apply** (роль manager или compliance) → Chat.

**vLLM (NVIDIA GPU):**

```powershell
make llm-vllm
# эквивалент: docker compose -f infra/docker-compose.yml --profile llm-gpu up -d vllm
```

UI: Provider `VLLM`, Base URL `http://vllm:8000/v1` (из compose) или `http://localhost:8000/v1` (с хоста), model `Qwen/Qwen2.5-7B-Instruct`.

> Profile `llm` поднимает только **Ollama**. vLLM вынесен в `llm-gpu`, чтобы случайно не тянуть multi-GB образ.

### A4. Роли и ACL в UI

В шапке Role:

| Role | Clearance |
|------|-----------|
| guest | public |
| associate | public + internal |
| manager | public + internal |
| compliance | + secret |

Проверка: manager не видит secret promo (`42%`); compliance видит.

---

## B. С Kubernetes (Docker Desktop + Helm)

### B1. Установка инструментов (Windows)

- Docker Desktop с **Enable Kubernetes**
- Helm 3, kubectl

```powershell
docker version
kubectl config use-context docker-desktop
kubectl get nodes
helm version
```

Legacy kind (опционально): `$env:KP_K8S='kind'` + [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation).

### B2. Подъём приложения

```powershell
cd yuit-docs-ai-architect-platform
.\scripts\k8s-up.ps1
```

Скрипт (режим `desktop` по умолчанию):

1. Собирает `kp-api:dev`, `kp-frontend:dev`
2. Ставит ingress-nginx (LoadBalancer на **:8088** — `:80` часто занят IIS)
3. `helm upgrade --install kp` с [values-desktop.yaml](../infra/helm/knowledge-platform/values-desktop.yaml)

### B3. Hosts и доступ

В `C:\Windows\System32\drivers\etc\hosts` (от администратора):

```
127.0.0.1 kp.local
```

| Что | URL |
|-----|-----|
| UI | http://kp.local:8088 |
| API health | http://kp.local:8088/api/health |

```powershell
curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health
```

Если без hosts — тот же curl с заголовком Host.

### B4. LLM в кластере

**MOCK** — по умолчанию (`values-desktop.yaml`).

**Ollama в кластере:**

```powershell
$env:KP_LLM = "ollama"
.\scripts\k8s-up.ps1
```

Используется [values-ollama.yaml](../infra/helm/knowledge-platform/values-ollama.yaml).

После старта:

```powershell
kubectl -n kp exec -it deploy/ollama -- ollama pull qwen2.5:1.5b-instruct
```

В UI `/llm`: Provider `OLLAMA`, Base URL `http://ollama:11434/v1`, Apply.

**vLLM** — GPU; на Desktop обычно не включают.

### B5. Основные команды

```powershell
# контекст Docker Desktop
kubectl config use-context docker-desktop
kubectl get nodes

# поды / сервисы / ingress
kubectl -n kp get pods
kubectl -n kp get pods -o wide
kubectl -n kp get pods -w                 # watch
kubectl -n kp get all,ingress
kubectl -n ingress-nginx get pods,svc

# детали и логи
kubectl -n kp describe pod <имя-пода>
kubectl -n kp logs deploy/api -f
kubectl -n kp logs deploy/frontend --tail=50
kubectl -n kp logs deploy/neo4j --tail=100

# exec в контейнер
kubectl -n kp exec -it deploy/api -- sh

# smoke через ingress (:8088; Host нужен если нет записи в hosts)
curl.exe -H "Host: kp.local" http://127.0.0.1:8088/api/health

# Helm
helm -n kp status kp
helm -n kp list
.\scripts\k8s-down.ps1                    # helm uninstall kp
```

Hosts (Windows, от администратора): `C:\Windows\System32\drivers\etc\hosts` → `127.0.0.1 kp.local`

### B6. Связка UI ↔ LLM в K8s

```
Browser → Ingress :8088 → Frontend
Browser → Ingress /api → API → Ollama/vLLM (Data Plane)
```

Фронт **не** ходит в Ollama напрямую; только `PUT /v1/llm/config` и Chat/Labels через API.


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
