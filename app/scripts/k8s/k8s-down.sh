#!/usr/bin/env bash
set -euo pipefail

echo "==> helm uninstall kp"
helm uninstall kp -n kp 2>/dev/null || true

if [[ "${KP_K8S:-desktop}" == "kind" ]]; then
  cluster=retailpartnerx-kp
  echo "==> kind delete cluster $cluster"
  kind delete cluster --name "$cluster" 2>/dev/null || true
else
  echo "==> Leaving docker-desktop cluster; ingress-nginx left installed (shared)"
  echo "    To reset K8s entirely: Docker Desktop → Settings → Kubernetes → Reset"
fi

echo "Done."
