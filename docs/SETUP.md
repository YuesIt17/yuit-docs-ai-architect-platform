# Настройка и запуск инфраструктуры

| Режим | Когда | Windows (PowerShell) | macOS (bash/zsh) |
|-------|-------|----------------------|------------------|
| **Hybrid (рекомендуется)** | Desktop / защита — **без дублей** | `.\app\scripts\hybrid\hybrid-up.ps1` | `bash app/scripts/hybrid/hybrid-up.sh` |
| **Только K8s** | MOCK, без Ollama/obs | `.\app\scripts\k8s\k8s-up.ps1` | `bash app/scripts/k8s/k8s-up.sh` |
| **DevSecOps lab** | Trivy / Semgrep / kubectl | `.\app\scripts\sec\sec-scan.ps1` | `bash app/scripts/sec/sec-scan.sh` |

> **`make`** (если установлен): на Windows вызывает `.ps1`, на macOS/Linux — `.sh`.

| Команда | Что делает |
|---------|------------|
| `make demo` | Hybrid: side-stack (Ollama + obs) + `k8s-up` |
| `make k8s-up` / `make k8s-down` | Только Kubernetes (поднять / снести) |
| `make side` | Compose side-stack: Ollama + observability |
| `make llm-ollama` | Ollama + pull `qwen2.5:0.5b` |
| `make obs` | Prometheus / Grafana / Loki / Tempo |
| `make up` | То же, что `make side` |
| `make down` | Снести Compose (`obs` + `llm`, с volumes) |
| `make sec-scan` | DevSecOps lab (Trivy / Semgrep / kubectl); alias: `sec-ops` |
| `make dev-mock` | API + UI на хосте, LLM=MOCK |
| `make dev-llm` | API + UI на хосте, Ollama в контейнере (`qwen2.5:0.5b`) |
| `make api` / `make frontend` | То же по отдельности: API (`:8080`) / UI (`npm run dev`) |
| `make seed` | Заполнить stores (`pipelines.seed_all`) |
| `make test` | Pytest backend |
| `make load-smoke` | Лёгкий нагрузочный smoke |

**Hybrid zero-overlap:** K8s = api/frontend/stores/**minio**; Compose = **ollama** + prometheus/grafana/loki/tempo. Схема: [ADR-006](../architecture/adr/ADR-006-observability.md) · [compose-dev](infra/compose-dev.md).

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
.\app\scripts\hybrid\hybrid-up.ps1
# = side-stack (ollama + obs) + k8s-up с KP_LLM=compose-ollama
```

**macOS**

```bash
cd yuit-docs-ai-architect-platform
bash app/scripts/hybrid/hybrid-up.sh
# или: make demo
```

| Что | URL |
|-----|-----|
| UI | http://kp.local:8088 |
| API health | http://kp.local:8088/api/health |
| Ollama | http://127.0.0.1:11434/v1/models |
| Grafana | http://127.0.0.1:3000 (admin / admin) → **KP Overview** + Explore Tempo/Loki |
| Prometheus | http://127.0.0.1:9090 |
| Tempo | http://127.0.0.1:3200 (OTLP :4317/:4318) |
| Loki | http://127.0.0.1:3100 |
| MinIO Console | http://127.0.0.1:30901 (NodePort, minioadmin / minioadmin) |
| Neo4j Browser | http://127.0.0.1:30474 (NodePort) |
| API /metrics | http://127.0.0.1:30080/metrics (NodePort) |

Side-stack отдельно:

**Windows**

```powershell
docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d
.\app\scripts\ollama\ollama-pull.ps1 -Model qwen2.5:0.5b
```

**macOS**

```bash
docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d
bash app/scripts/ollama/ollama-pull.sh qwen2.5:0.5b
```

LLM в UI: Provider `OLLAMA`, Base URL `http://host.docker.internal:11434/v1`, model `qwen2.5:0.5b`.

Снос:

**Windows**

```powershell
.\app\scripts\k8s\k8s-down.ps1
docker compose -f app/infra/docker-compose.yml --profile obs --profile llm down -v
```

**macOS**

```bash
bash app/scripts/k8s/k8s-down.sh
docker compose -f app/infra/docker-compose.yml --profile obs --profile llm down -v
# или: make k8s-down && make down
```

---

## B. DevSecOps lab (сканеры)

После hybrid / `k8s-up`:

| ОС | Команда |
|----|---------|
| Windows | `.\app\scripts\sec\sec-scan.ps1` или `make sec-scan` |
| macOS | `bash app/scripts/sec/sec-scan.sh` или `make sec-scan` |

Подробно: [infra/sec-ops.md](infra/sec-ops.md). Отчёты: `tmp/sec-ops/`.

---

## C. Локальная разработка API/UI на хосте

Stores на хосте не нужны: `STORE_BACKEND=memory` и `LLM_PROVIDER=MOCK` — значения по умолчанию в `kp/config.py`. Команды `make dev-mock` и `make dev-llm` выставляют их сами, поэтому `.env` эти значения не перебивает.

**Make** (из корня, GNU Make). Одна команда поднимает API и UI:

| Команда | Что запускает |
|---------|----------------|
| `make dev-mock` | `uvicorn --reload` + Vite, LLM=MOCK |
| `make dev-llm` | контейнер Ollama (`qwen2.5:0.5b`) + те же процессы, `LLM_PROVIDER=OLLAMA`, base URL `http://127.0.0.1:11434/v1` |

UI: http://127.0.0.1:5173 · API: http://127.0.0.1:8080. Ctrl+C останавливает API и Vite. Stores остаются `memory` — Neo4j/Qdrant не нужны. `dev-llm` не поднимает Kubernetes: Ollama только в Compose, API ходит на `127.0.0.1`, не на `host.docker.internal`.

По отдельности (два терминала): `make api` и `make frontend`. `make frontend` выставляет `VITE_API_BASE_URL=http://127.0.0.1:8080`, чтобы Vite ходил в API на хосте, а не в `/api` ingress.

Перед первым запуском: venv и `pip install -e ".[dev]"` в `app/backend`, `npm install` в `app/frontend`. `make api` берёт Python из `app/backend/.venv`, не из PATH. Для `dev-llm` нужен Docker Desktop.

**Windows**

```powershell
cd app/backend
.\.venv\Scripts\Activate.ps1
$env:LLM_PROVIDER = "MOCK"
$env:STORE_BACKEND = "memory"
uvicorn kp.main:app --reload --port 8080
```

```powershell
cd app/frontend
npm install
npm run dev
```

**macOS**

```bash
cd app/backend
source .venv/bin/activate
export LLM_PROVIDER=MOCK
export STORE_BACKEND=memory
uvicorn kp.main:app --reload --port 8080
```

```bash
cd app/frontend
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
| Grafana пустой | Dashboards: Knowledge Platform → **KP Overview**; `docker compose -f app/infra/docker-compose.yml --profile obs up -d` |
| Tempo / Loki пустые | Нужен chat traffic; OTel `host.docker.internal:4318`; Grafana Explore; rebuild `kp-api:dev` |
| Prometheus target DOWN | Scrape `host.docker.internal:30080/metrics` |

---

## Чеклист сдачи

1. Hybrid → http://kp.local:8088 (`hybrid-up.ps1` / `hybrid-up.sh`)
2. Chat MOCK/OLLAMA → citations
3. ACL manager vs compliance
4. Labels upload (MinIO in-cluster)
5. Observability: Prometheus `kp-api-k8s` UP → Grafana **KP Overview** → Explore Tempo `kp-api` / Loki после chat
6. (Опционально) Graph Neo4j Browser :30474
7. (Опционально) `make sec-scan` → отчёты в `tmp/sec-ops/`
