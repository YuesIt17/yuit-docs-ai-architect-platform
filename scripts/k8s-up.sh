#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CLUSTER=retailpartnerx-kp

command -v kind >/dev/null
command -v helm >/dev/null
command -v kubectl >/dev/null

if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config infra/kind/kind-config.yaml
fi

kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
# kind extraPortMappings land on control-plane; pin controller there (hostPort 80/443).
kubectl label node "${CLUSTER}-control-plane" ingress-ready=true --overwrite >/dev/null || true
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type merge \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/os":"linux","ingress-ready":"true"}}}}}'
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=180s

docker build -t kp-api:dev -f backend/Dockerfile .
docker build -t kp-frontend:dev frontend/
kind load docker-image kp-api:dev kp-frontend:dev --name "$CLUSTER"
if docker image inspect bitnamilegacy/minio:2025.7.23-debian-12-r5 >/dev/null 2>&1; then
  kind load docker-image bitnamilegacy/minio:2025.7.23-debian-12-r5 --name "$CLUSTER"
fi

EXTRA=()
if [[ "${KP_LLM:-}" == "compose-ollama" || "${KP_LLM:-}" == "ollama" ]]; then
  EXTRA+=(-f infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml)
fi

helm upgrade --install kp infra/helm/knowledge-platform -n kp --create-namespace "${EXTRA[@]}"

echo "Add hosts: 127.0.0.1 kp.local"
echo "Open http://kp.local:8088"
echo "API: http://kp.local:8088/api/health"
echo "Hybrid LLM: make llm-ollama + KP_LLM=compose-ollama"
echo "Obs: make obs (Compose)"
