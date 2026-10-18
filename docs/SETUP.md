# Настройка и запуск инфраструктуры

| Режим | Когда | Windows (PowerShell) | macOS (bash/zsh) |
|-------|-------|----------------------|------------------|
| **Hybrid (рекомендуется)** | Desktop / защита — **без дублей** | `.\scripts\hybrid-up.ps1` | `bash scripts/hybrid-up.sh` |
| **Только K8s** | MOCK, без Ollama/obs | `.\scripts\k8s-up.ps1` | `bash scripts/k8s-up.sh` |
| **DevSecOps lab** | Trivy / Semgrep / kubectl | `.\scripts\sec-scan.ps1` | `bash scripts/sec-scan.sh` |

> **`make`** (если установлен): на Windows вызывает `.ps1`, на macOS — `.sh`.  
> Примеры: `make demo`, `make sec-scan`, `make obs`, `make down`.

**Hybrid zero-overlap:** K8s = api/frontend/stores/**minio**; Compose = **ollama** + prometheus/grafana/jaeger.

Архитектура: **[docs/infra/](infra/)** · ops: **[SRE.md](SRE.md)** · security lab: **[infra/sec-ops.md](infra/sec-ops.md)**.

---

## Предварительные требования

- Docker Desktop (+ Kubernetes в Settings), Git, Helm 3, kubectl
- Python 3.11+ / Node 20+ — только для локальной разработки API/UI на хосте
- Опционально: GNU Make (`choco install make` / `brew install make`)

**Windows**

```powershell
docker version
helm version
kubectl version --client
kubectl config use-context docker-desktop
```

Hosts (admin): `C:\Windows\System32\drivers\etc\hosts` → `127.0.0.1 kp.local`

**macOS**

```bash
docker version
helm version
kubectl version --client
kubectl config use-context docker-desktop
# hosts (один раз):
sudo sh -c 'grep -q "kp.local" /etc/hosts || echo "127.0.0.1 kp.local" >> /etc/hosts'
```

---

## A. Hybrid (рекомендуется)

**Windows**

```powershell
cd yuit-docs-ai-architect-platform
.\scripts\hybrid-up.ps1
# = side-stack (ollama + obs) + k8s-up с KP_LLM=compose-ollama
```

**macOS**

```bash
cd yuit-docs-ai-architect-platform
bash scripts/hybrid-up.sh
# или: make demo
```

| Что | URL |
|-----|-----|
| UI | http://kp.local:8088 |
| API health | http://kp.local:8088/api/health |
| Ollama | http://127.0.0.1:11434/v1/models |
| Jaeger | http://127.0.0.1:16686 |
| Prometheus | http://127.0.0.1:9090 |
| Grafana | http://127.0.0.1:3000 (admin / admin) → dashboard **KP Overview** |
| MinIO Console | http://127.0.0.1:30901 (NodePort, minioadmin / minioadmin) |
| Neo4j Browser | http://127.0.0.1:30474 (NodePort) |
| API /metrics | http://127.0.0.1:30080/metrics (NodePort) |

Side-stack отдельно:

**Windows**

```powershell
docker compose -f infra/docker-compose.yml --profile llm --profile obs up -d
.\scripts\ollama-pull.ps1 -Model qwen2.5:0.5b
```

**macOS**

```bash
docker compose -f infra/docker-compose.yml --profile llm --profile obs up -d
bash scripts/ollama-pull.sh qwen2.5:0.5b
```

LLM в UI: Provider `OLLAMA`, Base URL `http://host.docker.internal:11434/v1`, model `qwen2.5:0.5b`.

Снос:

**Windows**

```powershell
.\scripts\k8s-down.ps1
docker compose -f infra/docker-compose.yml --profile obs --profile llm down -v
```

**macOS**

```bash
bash scripts/k8s-down.sh
docker compose -f infra/docker-compose.yml --profile obs --profile llm down -v
# или: make k8s-down && make down
```

---

## B. DevSecOps lab (сканеры)

После hybrid / `k8s-up`:

| ОС | Команда |
|----|---------|
| Windows | `.\scripts\sec-scan.ps1` или `make sec-scan` |
| macOS | `bash scripts/sec-scan.sh` или `make sec-scan` |

Подробно: [infra/sec-ops.md](infra/sec-ops.md). Отчёты: `tmp/sec-ops/`.

---

## C. Локальная разработка API/UI на хосте

Stores на хосте не нужны: ниже `STORE_BACKEND=memory`.

**Windows**

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

**macOS**

```bash
cd backend
source .venv/bin/activate
export LLM_PROVIDER=MOCK
export STORE_BACKEND=memory
uvicorn app.main:app --reload --port 8080
```

```bash
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
| `LLM_PROVIDER` | MOCK / OLLAMA | overlay / UI Apply |
| `OPENAI_BASE_URL` | endpoint из **пода API** | `http://host.docker.internal:11434/v1` |
| `STORE_BACKEND` | memory / live | `live` в K8s desktop |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | traces (OTLP/HTTP) | `http://host.docker.internal:4318` |

---

## Типичные проблемы

| Симптом | Что сделать |
|---------|-------------|
| OLLAMA unreachable | Base URL `host.docker.internal`, не `localhost` из пода |
| Ingress `:8088` 404 IIS (Windows) | Hosts `kp.local`, LB на 8088 |
| `ollama pull` TLS timeout | `ollama-pull.ps1` / `ollama-pull.sh` |
| MinIO 9000 на хосте пусто | MinIO в K8s → Console NodePort `:30901` |
| Grafana пустой | Dashboards: Knowledge Platform → **KP Overview**; `docker compose -f infra/docker-compose.yml --profile obs up -d` |
| Jaeger пустой | Нужен chat traffic; OTel `host.docker.internal:4318`; rebuild `kp-api:dev` |
| Prometheus target DOWN | Scrape `host.docker.internal:30080/metrics` |

---

## Чеклист сдачи

1. Hybrid → http://kp.local:8088 (`hybrid-up.ps1` / `hybrid-up.sh`)
2. Chat MOCK/OLLAMA → citations
3. ACL manager vs compliance
4. Labels upload (MinIO in-cluster)
5. Observability: Prometheus `kp-api-k8s` UP → Grafana **KP Overview** → Jaeger `kp-api` после chat
6. (Опционально) Graph Neo4j Browser :30474
7. (Опционально) `make sec-scan` → отчёты в `tmp/sec-ops/`
