.PHONY: up down demo seed test api frontend llm-ollama llm-vllm k8s-up k8s-down load-smoke

up:
	docker compose -f infra/docker-compose.yml --profile core up -d --build

down:
	docker compose -f infra/docker-compose.yml --profile core --profile demo --profile llm --profile llm-gpu --profile vision down -v

demo:
	docker compose -f infra/docker-compose.yml --profile demo up -d --build

seed:
	cd backend && python -m pipelines.seed_all

api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

frontend:
	cd frontend && npm run dev

llm-ollama:
	docker compose -f infra/docker-compose.yml --profile demo --profile llm up -d --build ollama api frontend
	powershell -ExecutionPolicy Bypass -File scripts/ollama-pull.ps1 -Model qwen2.5:1.5b-instruct
	@echo "Set in UI /llm: OLLAMA base_url=http://ollama:11434/v1 (from api container) or http://localhost:11434/v1"

# Profile llm-gpu (not llm) so plain --profile llm does not pull multi-GB vLLM.
llm-vllm:
	docker compose -f infra/docker-compose.yml --profile demo --profile llm-gpu up -d --build vllm api frontend
	@echo "Set in UI /llm: VLLM base_url=http://vllm:8000/v1"

test:
	cd backend && pytest -q

evals:
	cd backend && pytest ../evals -q

load-smoke:
	cd backend && python -m scripts.load_smoke

k8s-up:
	powershell -ExecutionPolicy Bypass -File scripts/k8s-up.ps1

k8s-down:
	powershell -ExecutionPolicy Bypass -File scripts/k8s-down.ps1
