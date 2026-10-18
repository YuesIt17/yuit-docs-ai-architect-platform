.PHONY: up down demo seed test api frontend llm-ollama obs side k8s-up k8s-down load-smoke sec-scan sec-ops

# Windows: PowerShell scripts; macOS/Linux: bash scripts
ifeq ($(OS),Windows_NT)
  RUN_PS = powershell -ExecutionPolicy Bypass -File
  demo:
	$(RUN_PS) app/scripts/hybrid/hybrid-up.ps1
  llm-ollama:
	docker compose -f app/infra/docker-compose.yml --profile llm up -d ollama
	$(RUN_PS) app/scripts/ollama/ollama-pull.ps1 -Model qwen2.5:0.5b
	@echo "K8s API -> OLLAMA http://host.docker.internal:11434/v1 model=qwen2.5:0.5b"
  k8s-up:
	$(RUN_PS) app/scripts/k8s/k8s-up.ps1
  k8s-down:
	$(RUN_PS) app/scripts/k8s/k8s-down.ps1
  sec-scan sec-ops:
	$(RUN_PS) app/scripts/sec/sec-scan.ps1
else
  demo:
	bash app/scripts/hybrid/hybrid-up.sh
  llm-ollama:
	docker compose -f app/infra/docker-compose.yml --profile llm up -d ollama
	bash app/scripts/ollama/ollama-pull.sh qwen2.5:0.5b
	@echo "K8s API -> OLLAMA http://host.docker.internal:11434/v1 model=qwen2.5:0.5b"
  k8s-up:
	bash app/scripts/k8s/k8s-up.sh
  k8s-down:
	bash app/scripts/k8s/k8s-down.sh
  sec-scan sec-ops:
	bash app/scripts/sec/sec-scan.sh
endif

# Compose side-stack only
side: llm-ollama obs

obs:
	docker compose -f app/infra/docker-compose.yml --profile obs up -d

up: side

down:
	docker compose -f app/infra/docker-compose.yml --profile obs --profile llm down -v

seed:
	cd app/backend && python -m pipelines.seed_all

api:
	cd app/backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

frontend:
	cd app/frontend && npm run dev

test:
	cd app/backend && pytest -q

load-smoke:
	cd app/backend && python -m scripts.load_smoke
