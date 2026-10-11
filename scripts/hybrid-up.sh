#!/usr/bin/env bash
# Clean hybrid: Compose side-stack (Ollama + obs) + Desktop K8s platform.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Compose side-stack (ollama + prometheus/grafana/jaeger)"
docker compose -f infra/docker-compose.yml --profile llm --profile obs up -d --remove-orphans
bash "$ROOT/scripts/ollama-pull.sh" qwen2.5:0.5b

echo "==> Kubernetes platform (api/frontend/stores/minio) + OLLAMA overlay"
export KP_LLM=compose-ollama
bash "$ROOT/scripts/k8s-up.sh"

cat <<'EOF'

Hybrid ready (no Compose↔K8s duplicates):
  UI     http://kp.local:8088
  API    http://kp.local:8088/api/health
  Ollama http://127.0.0.1:11434/v1/models
  Jaeger http://127.0.0.1:16686
  Prom   http://127.0.0.1:9090
  Graf   http://127.0.0.1:3000

Do NOT run make demo-standalone while K8s is up.
EOF
