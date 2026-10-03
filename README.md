# RetailPartnerX Knowledge Platform

FAANG-style **GraphRAG + multimodal** knowledge platform for **RetailPartnerX** (global FMCG retail).  
Google PE principles: Control Plane / Data Plane, paved road (`docker compose`), Security-by-Design (RBAC on chunks), air-gapped LLM.

Continuity of [yuit-docs-ai-architect](https://github.com/YuesIt17/yuit-docs-ai-architect) (hw-1…hw-10).

## Quick start (local, no GPU)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8080
```

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/v1/chat ^
  -H "Authorization: Bearer manager" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Какие аллергены у FreshFarm oats?\",\"stream\":false}"
```

Label (fixture as PNG name):

```bash
curl -X POST http://localhost:8080/v1/vision/label ^
  -H "Authorization: Bearer associate" ^
  -F "file=@../datasets/fixtures/label.png.txt;filename=label.png"
```

Demo tokens: `guest` | `associate` | `manager` | `compliance`

## Stack compose

```bash
cp .env.example .env
make demo   # core data plane + api + seed profile
```

| Service | Port |
|---------|------|
| API | 8080 |
| Neo4j Browser | 7474 |
| Qdrant | 6333 |
| MinIO API / Console | 9000 / 9001 |
| Jaeger | 16686 |
| Prometheus | 9090 |
| Grafana | 3000 |

LLM profiles: `--profile llm` (vLLM/Ollama). Default API uses **MOCK** LLM (no cloud APIs).

## Monorepo

```
/infra     docker-compose, prometheus, grafana, vault stub
/backend   FastAPI + LangGraph + pipelines + tests
/docs      ADD (C4, ADR, ER, sequences, Model Card)
/datasets  seed KB + label fixtures
/evals     LLM-as-Judge stubs
```

## Documentation

- [Executive summary](docs/00-executive-summary.md)
- [C4 Context](docs/architecture/c4-context.md) · [Containers](docs/architecture/c4-container.md) · [Components](docs/architecture/c4-component.md)
- [Deployment](docs/architecture/deployment.md) · [Data flow](docs/architecture/data-flow.md)
- [ADRs](docs/adr/) · [Demo script](docs/demo-script.md) · [Load report](docs/load-report.md)

## Tests

```bash
cd backend && pytest -q
pytest ../evals -q
```

## Author

Evgeny Yulov — Platform Engineer / AI Architect case study.
