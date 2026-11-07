#!/usr/bin/env bash
# Docker Desktop Kubernetes (default) or kind:
#   KP_K8S=desktop   # default
#   KP_K8S=kind
# Real login with Keycloak and the BFF, on Docker Desktop only:
#   KP_AUTH=oidc
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

mode="$(echo "${KP_K8S:-desktop}" | tr '[:upper:]' '[:lower:]')"
auth="$(echo "${KP_AUTH:-demo}" | tr '[:upper:]' '[:lower:]')"
if [[ "$auth" == "oidc" && "$mode" == "kind" ]]; then
  echo "KP_AUTH=oidc is set up for Docker Desktop only (values-desktop-oidc.yaml)." >&2
  exit 1
fi

echo "==> Checking tools"
for cmd in helm kubectl docker; do
  command -v "$cmd" >/dev/null || { echo "Missing required command: $cmd" >&2; exit 1; }
done
if [[ "$mode" == "kind" ]]; then
  command -v kind >/dev/null || { echo "Missing kind (or set KP_K8S=desktop)" >&2; exit 1; }
fi

echo "==> Building images"
docker build -t kp-api:dev -f app/backend/Dockerfile .
docker build -t kp-frontend:dev app/frontend/
if [[ "$auth" == "oidc" ]]; then
  docker build -t kp-bff:dev app/bff/
  docker build -t kp-keycloak:dev app/infra/keycloak/
fi

values=()
if [[ "$mode" == "kind" ]]; then
  cluster=retailpartnerx-kp
  if ! kind get clusters 2>/dev/null | grep -qx "$cluster"; then
    echo "==> Creating kind cluster $cluster"
    kind create cluster --config app/infra/kind/kind-config.yaml
  else
    echo "==> kind cluster $cluster already exists"
  fi

  echo "==> Ensuring ingress-nginx (kind)"
  kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
  kubectl label node "${cluster}-control-plane" ingress-ready=true --overwrite >/dev/null || true
  kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type merge \
    -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/os":"linux","ingress-ready":"true"}}}}}'
  kubectl wait --namespace ingress-nginx --for=condition=ready pod \
    --selector=app.kubernetes.io/component=controller --timeout=180s

  echo "==> Loading images into kind"
  kind load docker-image kp-api:dev kp-frontend:dev --name "$cluster"
  if docker image inspect bitnamilegacy/minio:2025.7.23-debian-12-r5 >/dev/null 2>&1; then
    kind load docker-image bitnamilegacy/minio:2025.7.23-debian-12-r5 --name "$cluster"
  fi
else
  echo "==> Using Docker Desktop Kubernetes context"
  kubectl config use-context docker-desktop >/dev/null
  if ! kubectl get nodes --request-timeout=10s >/dev/null 2>&1; then
    echo "docker-desktop context not ready. Enable Kubernetes in Docker Desktop Settings." >&2
    exit 1
  fi

  echo "==> Ensuring ingress-nginx (LoadBalancer -> localhost :8088)"
  helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
  helm repo update ingress-nginx
  helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
    --namespace ingress-nginx --create-namespace \
    --set controller.service.type=LoadBalancer \
    --set controller.service.ports.http=8088 \
    --set controller.service.ports.https=8443 \
    --wait --timeout 5m

  # Docker Desktop can run Kubernetes as a kind cluster named "desktop". Its node does not see images built
  # with `docker build`, so pods would fail with ErrImageNeverPull until the images are loaded.
  if command -v kind >/dev/null && kind get clusters 2>/dev/null | grep -qx desktop; then
    images=(kp-api:dev kp-frontend:dev)
    if [[ "$auth" == "oidc" ]]; then
      images+=(kp-bff:dev kp-keycloak:dev)
    fi
    echo "==> Loading local images into the Docker Desktop kind node (takes a few minutes)"
    kind load docker-image "${images[@]}" --name desktop
  elif docker ps --format '{{.Names}}' | grep -qx desktop-control-plane; then
    echo "WARN: Docker Desktop runs Kubernetes with kind, but the kind CLI is missing. Install it, or pods fail with ErrImageNeverPull." >&2
  fi

  values+=(-f app/infra/helm/knowledge-platform/values-desktop.yaml)
fi

extra=()
if [[ "${KP_LLM:-}" == "compose-ollama" || "${KP_LLM:-}" == "ollama" ]]; then
  if [[ "${KP_LLM:-}" == "ollama" ]]; then
    echo "WARN: KP_LLM=ollama (in-cluster) removed. Use compose-ollama + make llm-ollama." >&2
  fi
  extra+=(-f app/infra/helm/knowledge-platform/values-desktop-compose-ollama.yaml)
fi

if [[ "$auth" == "oidc" ]]; then
  extra+=(-f app/infra/helm/knowledge-platform/values-desktop-oidc.yaml)
fi

echo "==> Helm upgrade --install kp"
helm upgrade --install kp app/infra/helm/knowledge-platform \
  -n kp --create-namespace \
  "${values[@]+"${values[@]}"}" \
  "${extra[@]+"${extra[@]}"}" \
  --wait --timeout 5m

# Mutable tags (kp-*:dev) + imagePullPolicy Never: Helm spec unchanged → pods keep old digest.
echo "==> Rollout restart api/frontend (pick up rebuilt :dev images)"
kubectl -n kp rollout restart deploy/api deploy/frontend
kubectl -n kp rollout status deploy/api --timeout=120s
kubectl -n kp rollout status deploy/frontend --timeout=120s
if [[ "$auth" == "oidc" ]]; then
  kubectl -n kp rollout restart deploy/bff
  kubectl -n kp rollout status deploy/bff --timeout=120s
fi

if [[ "$auth" == "oidc" ]]; then
  cat <<EOF

Done (mode=$mode, auth=oidc). No hosts entry is needed: browsers resolve *.localhost themselves.
  UI  http://kp.localhost:8088/
  Demo users are in app/infra/helm/knowledge-platform/values-desktop-oidc.yaml
  Check: python app/scripts/k8s/oidc_e2e.py
EOF
  exit 0
fi

cat <<EOF

Done (mode=$mode).
Add hosts: 127.0.0.1 kp.local
  macOS:   sudo sh -c 'grep -q "kp.local" /etc/hosts || echo "127.0.0.1 kp.local" >> /etc/hosts'
  Windows: edit C:\\Windows\\System32\\drivers\\etc\\hosts (admin)

Docker Desktop:
  UI  http://kp.local:8088/
  API http://kp.local:8088/api/health
  Or: curl -H "Host: kp.local" http://127.0.0.1:8088/api/health

Hybrid LLM: make llm-ollama; then KP_LLM=compose-ollama make k8s-up
Observability: make obs  (Prometheus / Grafana / Loki / Tempo — Compose only)
EOF
