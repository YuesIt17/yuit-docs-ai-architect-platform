# RetailPartnerX Knowledge Platform

FAANG-style **GraphRAG + multimodal** knowledge platform for **RetailPartnerX** (global FMCG retail).

- **Control Plane:** FastAPI + LangGraph + Guardrails + LLM runtime API  
- **Data Plane:** Neo4j / Qdrant / MinIO / Postgres / Redis + **Ollama/vLLM**  
- **UI:** React + TypeScript (Chat, Labels, **LLM Settings**, Graph, Ops)

## Setup guide (Compose + Kubernetes)

Полная инструкция: **[docs/SETUP.md](docs/SETUP.md)** — настройка **без K8s** и **с kind/Helm**, LLM (Ollama/vLLM), ACL, troubleshooting.

## Quick start (dev)

### API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1   # or: python -m venv .venv && pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` → `:8080`.

Demo tokens (Role switcher): `guest` | `associate` | `manager` | `compliance`

### LLM UI

1. Open **LLM** page  
2. Choose `MOCK` / `OLLAMA` / `VLLM`, Probe, Apply (manager/compliance)  
3. Chat/Labels use the active provider; answers show `model_uri`

```powershell
# local Ollama (Docker)
make llm-ollama
# then in UI: provider=OLLAMA, base_url=http://localhost:11434/v1
```

## Docker Compose

```powershell
make demo          # data plane + api + frontend (:5173)
make llm-ollama    # + ollama (:11434)
make down
```

| Service | Port |
|---------|------|
| Frontend | 5173 |
| API | 8080 |
| Neo4j | 7474 |
| MinIO console | 9001 |
| Jaeger | 16686 |
| Ollama (profile llm) | 11434 |

## Kubernetes (kind + Helm)

```powershell
.\scripts\k8s-up.ps1
# hosts: 127.0.0.1 kp.local
# UI: http://kp.local:8088
```

With in-cluster Ollama:

```powershell
$env:KP_LLM = "ollama"
.\scripts\k8s-up.ps1
```

See [docs/architecture/k8s-deployment.md](docs/architecture/k8s-deployment.md).

## Docs

- [Executive summary](docs/00-executive-summary.md)
- [C4 / Deployment / ADRs](docs/)
- [Demo script](docs/demo-script.md)
- [Load report](docs/load-report.md)

## Tests

```powershell
cd backend; pytest -q
```

## Author

Evgeny Yulov — Platform Engineer / AI Architect case study.
