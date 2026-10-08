.PHONY: up down demo demo-standalone seed test api frontend llm-ollama llm-vllm obs side k8s-up k8s-down load-smoke

# Clean hybrid (default): Compose side-stack + K8s platform — no overlapping services
demo:
	powershell -ExecutionPolicy Bypass -File scripts/hybrid-up.ps1

# Compose side-stack only
side: llm-ollama obs

obs:
	docker compose -f infra/docker-compose.yml --profile obs up -d

llm-ollama:
	docker compose -f infra/docker-compose.yml --profile llm up -d ollama
	powershell -ExecutionPolicy Bypass -File scripts/ollama-pull.ps1 -Model qwen2.5:0.5b
	@echo "K8s API → OLLAMA http://host.docker.internal:11434/v1 model=qwen2.5:0.5b"

llm-vllm:
	docker compose -f infra/docker-compose.yml --profile llm-gpu up -d vllm
	@echo "From K8s API: VLLM http://host.docker.internal:8000/v1"

# Full stack WITHOUT Kubernetes (mutually exclusive with k8s-up)
demo-standalone:
	docker compose -f infra/docker-compose.standalone.yml up -d --build

up: side

down:
	docker compose -f infra/docker-compose.yml --profile obs --profile llm --profile llm-gpu down -v
	-docker compose -f infra/docker-compose.standalone.yml down -v

seed:
	cd backend && python -m pipelines.seed_all

api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

frontend:
	cd frontend && npm run dev

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
