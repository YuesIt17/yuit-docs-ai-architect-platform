.PHONY: up down demo demo-standalone seed test api frontend llm-ollama obs side k8s-up k8s-down load-smoke sec-scan sec-ops

# Windows: PowerShell scripts; macOS/Linux: bash scripts
ifeq ($(OS),Windows_NT)
  RUN_PS = powershell -ExecutionPolicy Bypass -File
  demo:
	$(RUN_PS) scripts/hybrid-up.ps1
  llm-ollama:
	docker compose -f infra/docker-compose.yml --profile llm up -d ollama
	$(RUN_PS) scripts/ollama-pull.ps1 -Model qwen2.5:0.5b
	@echo "K8s API -> OLLAMA http://host.docker.internal:11434/v1 model=qwen2.5:0.5b"
  k8s-up:
	$(RUN_PS) scripts/k8s-up.ps1
  k8s-down:
	$(RUN_PS) scripts/k8s-down.ps1
  sec-scan sec-ops:
	$(RUN_PS) scripts/sec-scan.ps1
else
  demo:
	bash scripts/hybrid-up.sh
  llm-ollama:
	docker compose -f infra/docker-compose.yml --profile llm up -d ollama
	bash scripts/ollama-pull.sh qwen2.5:0.5b
	@echo "K8s API -> OLLAMA http://host.docker.internal:11434/v1 model=qwen2.5:0.5b"
  k8s-up:
	bash scripts/k8s-up.sh
  k8s-down:
	bash scripts/k8s-down.sh
  sec-scan sec-ops:
	bash scripts/sec-scan.sh
endif

# Compose side-stack only
side: llm-ollama obs

obs:
	docker compose -f infra/docker-compose.yml --profile obs up -d

# Full stack WITHOUT Kubernetes (mutually exclusive with k8s-up)
demo-standalone:
	docker compose -f infra/docker-compose.standalone.yml up -d --build

up: side

down:
	docker compose -f infra/docker-compose.yml --profile obs --profile llm down -v
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
