.PHONY: up down demo seed test api frontend dev-mock dev-llm llm-ollama obs side k8s-up k8s-down load-smoke sec-scan sec-ops

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

# uvicorn/pytest live in app/backend/.venv, not on PATH.
# cmd.exe treats "/" as a switch, so ".venv/Scripts/python.exe" runs the command ".venv".
ifeq ($(OS),Windows_NT)
  VENV_PY := .venv\Scripts\python.exe
else
  VENV_PY := .venv/bin/python
endif

seed:
	cd app/backend && $(VENV_PY) -m pipelines.seed_all

api:
	cd app/backend && $(VENV_PY) -m uvicorn kp.main:app --reload --host 0.0.0.0 --port 8080

frontend: export VITE_API_BASE_URL := http://127.0.0.1:8080
frontend:
	cd app/frontend && npm run dev

# Host API + Vite. Ctrl+C stops both. Stores stay in-memory.
dev-mock: export LLM_PROVIDER := MOCK
dev-mock: export STORE_BACKEND := memory
dev-mock:
	@echo "API  http://127.0.0.1:8080  LLM=MOCK"
	@echo "UI   http://127.0.0.1:5173"
	$(MAKE) -j2 api frontend

# Same processes; Ollama container on :11434 (API on the host calls 127.0.0.1, not host.docker.internal).
dev-llm: export LLM_PROVIDER := OLLAMA
dev-llm: export OPENAI_BASE_URL := http://127.0.0.1:11434/v1
dev-llm: export LLM_MODEL := qwen2.5:0.5b
dev-llm: export STORE_BACKEND := memory
dev-llm: llm-ollama
	@echo "API  http://127.0.0.1:8080  LLM=OLLAMA http://127.0.0.1:11434/v1 model=qwen2.5:0.5b"
	@echo "UI   http://127.0.0.1:5173"
	$(MAKE) -j2 api frontend

test:
	cd app/backend && $(VENV_PY) -m pytest -q

load-smoke:
	cd app/backend && $(VENV_PY) -m scripts.load_smoke
