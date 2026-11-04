# Infrastructure Setup and Startup

| Mode | When | Windows (PowerShell) | macOS (bash/zsh) |
|-------|-------|----------------------|------------------|
| **Hybrid (recommended)** | Desktop / demo, **no duplicate services** | `.\app\scripts\hybrid\hybrid-up.ps1` | `bash app/scripts/hybrid/hybrid-up.sh` |
| **K8s only** | MOCK, without Ollama/obs | `.\app\scripts\k8s\k8s-up.ps1` | `bash app/scripts/k8s/k8s-up.sh` |
| **DevSecOps lab** | Trivy / Semgrep / kubectl | `.\app\scripts\sec\sec-scan.ps1` | `bash app/scripts/sec/sec-scan.sh` |

> **`make`** (if installed): runs `.ps1` on Windows and `.sh` on macOS/Linux.

| Command | What it does |
|---------|------------|
| `make demo` | Hybrid: side-stack (Ollama + obs) + `k8s-up` |
| `make k8s-up` / `make k8s-down` | Kubernetes only (bring up / tear down) |
| `make side` | Compose side-stack: Ollama + observability |
| `make llm-ollama` | Ollama + pull `qwen2.5:0.5b` (desktop) |
| Compose `--profile vllm` | Submission vLLM AWQ profile — see [infra/vllm-profile.md](infra/vllm-profile.md); GPU **runtime not verified** without NVIDIA |
| `make obs` | Prometheus / Grafana / Loki / Tempo / Alloy |
| `make up` | Same as `make side` |
| `make down` | Tear down Compose (`obs` + `llm`, with volumes) |
| `make sec-scan` | DevSecOps lab (Trivy / Semgrep / kubectl); alias: `sec-ops` |
| `make dev-mock` | API + UI on the host, LLM=MOCK |
| `make dev-llm` | API + UI on the host, Ollama in a container (`qwen2.5:0.5b`) |
| `make api` / `make frontend` | The same, separately: API (`:8080`) / UI (`npm run dev`) |
| `make seed` | Populate stores (`pipelines.seed_all`) |
| `make test` | Pytest backend |
| `make load-smoke` | Lightweight load smoke test |

**Hybrid zero-overlap:** K8s = api/frontend/stores/**minio**; Compose = **ollama** + prometheus/grafana/loki/tempo. Diagram: [ADR-006](../architecture/adr/ADR-006-observability.md) · [compose-dev](infra/compose-dev.md).

Architecture: **[docs/infra/](infra/)** · ops: **[SRE.md](SRE.md)** · security lab: **[infra/sec-ops.md](infra/sec-ops.md)**.

---

## Prerequisites

- Docker Desktop (+ Kubernetes in Settings), Git, Helm 3, kubectl
- Python 3.11+ / Node 20+, only for local API/UI development on the host
- Optional: GNU Make (`choco install make` / `brew install make`)

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
# hosts (once):
sudo sh -c 'grep -q "kp.local" /etc/hosts || echo "127.0.0.1 kp.local" >> /etc/hosts'
```

---

## A. Hybrid (recommended)

**Windows**

```powershell
cd yuit-docs-ai-architect-platform
.\app\scripts\hybrid\hybrid-up.ps1
# = side-stack (ollama + obs) + k8s-up with KP_LLM=compose-ollama
```

**macOS**

```bash
cd yuit-docs-ai-architect-platform
bash app/scripts/hybrid/hybrid-up.sh
# or: make demo
```

| What | URL |
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

Side-stack on its own:

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

LLM in the UI: Provider `OLLAMA`, Base URL `http://host.docker.internal:11434/v1`, model `qwen2.5:0.5b`.

Teardown:

**Windows**

```powershell
.\app\scripts\k8s\k8s-down.ps1
docker compose -f app/infra/docker-compose.yml --profile obs --profile llm down -v
```

**macOS**

```bash
bash app/scripts/k8s/k8s-down.sh
docker compose -f app/infra/docker-compose.yml --profile obs --profile llm down -v
# or: make k8s-down && make down
```

---

## B. DevSecOps lab (scanners)

After hybrid / `k8s-up`:

| OS | Command |
|----|---------|
| Windows | `.\app\scripts\sec\sec-scan.ps1` or `make sec-scan` |
| macOS | `bash app/scripts/sec/sec-scan.sh` or `make sec-scan` |

Details: [infra/sec-ops.md](infra/sec-ops.md). Reports: `tmp/sec-ops/`.

---

## C. Local API/UI development on the host

No stores are needed on the host: `STORE_BACKEND=memory` and `LLM_PROVIDER=MOCK` are the defaults in `kp/config.py`. `make dev-mock` and `make dev-llm` set them explicitly, so `.env` does not override these values.

**Make** (from the repo root, GNU Make). One command brings up the API and UI:

| Command | What it starts |
|---------|----------------|
| `make dev-mock` | `uvicorn --reload` + Vite, LLM=MOCK |
| `make dev-llm` | Ollama container (`qwen2.5:0.5b`) + the same processes, `LLM_PROVIDER=OLLAMA`, base URL `http://127.0.0.1:11434/v1` |

UI: http://127.0.0.1:5173 · API: http://127.0.0.1:8080. Ctrl+C stops the API and Vite. Stores stay in `memory`, so Neo4j/Qdrant are not needed. `dev-llm` does not start Kubernetes: Ollama runs only in Compose, and the API calls `127.0.0.1`, not `host.docker.internal`.

Separately (two terminals): `make api` and `make frontend`. `make frontend` sets `VITE_API_BASE_URL=http://127.0.0.1:8080` so that Vite calls the API on the host rather than the `/api` ingress.

Before the first run: create a venv and run `pip install -e ".[dev]"` in `app/backend`, and `npm install` in `app/frontend`. `make api` takes Python from `app/backend/.venv`, not from PATH. `dev-llm` requires Docker Desktop.

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

## Roles and ACL

| Role | Clearance |
|------|-----------|
| guest | public |
| associate / manager | public + internal |
| compliance | + secret |

manager cannot see the secret promo (`42%`); compliance can.

---

## Variables

See [.env.example](../.env.example).

| Variable | Meaning | Hybrid |
|------------|-------|--------|
| `LLM_PROVIDER` | MOCK / OLLAMA | overlay / UI Apply |
| `OPENAI_BASE_URL` | endpoint from the **API pod** | `http://host.docker.internal:11434/v1` |
| `STORE_BACKEND` | memory / live | `live` in K8s desktop |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | traces (OTLP/HTTP) | `http://host.docker.internal:4318` |

---

## Common problems

| Symptom | What to do |
|---------|-------------|
| `kubectl`: `Unable to connect to the server: EOF` | A system proxy is intercepting the request. Add `kubernetes.docker.internal` to `NO_PROXY` |
| OLLAMA unreachable | Base URL `host.docker.internal`, not `localhost` from the pod |
| Ingress `:8088` 404 IIS (Windows) | Hosts `kp.local`, LB on 8088 |
| `ollama pull` TLS timeout | `ollama-pull.ps1` / `ollama-pull.sh` |
| MinIO 9000 on the host is empty | MinIO is in K8s → Console NodePort `:30901` |
| Grafana is empty | Dashboards: Knowledge Platform → **KP Overview**; `docker compose -f app/infra/docker-compose.yml --profile obs up -d` |
| Tempo / Loki are empty | Chat traffic is required; OTel `host.docker.internal:4318`; Grafana Explore; rebuild `kp-api:dev` |
| Prometheus target DOWN | Scrape `host.docker.internal:30080/metrics` |

---

## Submission checklist

1. Hybrid → http://kp.local:8088 (`hybrid-up.ps1` / `hybrid-up.sh`)
2. Chat MOCK/OLLAMA → citations
3. ACL manager vs compliance
4. Labels upload (MinIO in-cluster)
5. Observability: Prometheus `kp-api-k8s` UP → Grafana **KP Overview** → Explore Tempo `kp-api` / Loki after chat
6. (Optional) Graph Neo4j Browser :30474
7. (Optional) `make sec-scan` → reports in `tmp/sec-ops/`
