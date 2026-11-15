#!/usr/bin/env bash
# Clean hybrid: Compose side-stack (Ollama + obs) + Desktop K8s platform.
# Real login with Keycloak and the BFF is the default. For the demo role switcher instead:
#   KP_AUTH=demo make demo
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

export KP_AUTH="${KP_AUTH:-oidc}"

echo "==> Compose side-stack (ollama + prometheus/grafana/tempo/loki)"
docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d --remove-orphans
bash "$ROOT/app/scripts/ollama/ollama-pull.sh" qwen2.5:0.5b

echo "==> Kubernetes platform (api/frontend/stores/minio) + OLLAMA overlay, auth=$KP_AUTH"
export KP_LLM=compose-ollama
bash "$ROOT/app/scripts/k8s/k8s-up.sh"

if [[ "$KP_AUTH" == "oidc" ]]; then
  ui="http://kp.localhost:8088"
  login="  Login  users and passwords are in app/infra/helm/knowledge-platform/values-desktop-oidc.yaml"
else
  ui="http://kp.local:8088"
  login="  Login  none: pick a role in the UI (KP_AUTH=demo)"
fi

cat <<EOF

Hybrid ready (Compose and Kubernetes run no duplicate services):
  UI     $ui
  API    $ui/api/health
$login
  Ollama http://127.0.0.1:11434/v1/models
  Graf   http://127.0.0.1:3000  (Explore: Tempo + Loki)
  Prom   http://127.0.0.1:9090
  Tempo  http://127.0.0.1:3200
  Loki   http://127.0.0.1:3100
EOF
