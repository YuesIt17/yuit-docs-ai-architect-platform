#!/usr/bin/env bash
# Stable access to kind ingress when Docker Desktop hostPort mappings flap.
# Usage: ./scripts/k8s-expose.sh
set -euo pipefail
PORT="${PORT:-8088}"
NS="${NS:-ingress-nginx}"
SVC="${SVC:-ingress-nginx-controller}"

echo "==> Exposing ingress on 127.0.0.1:${PORT} (Ctrl+C to stop)"
echo "    UI http://kp.local:${PORT}  API http://127.0.0.1:${PORT}/api/health"

while true; do
  if curl -fsS -m 3 -H "Host: kp.local" "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    sleep 5
    continue
  fi
  echo "$(date +%H:%M:%S) restarting port-forward"
  pkill -f "port-forward svc/${SVC} ${PORT}:80" 2>/dev/null || true
  kubectl -n "$NS" port-forward "svc/${SVC}" "${PORT}:80" --address=127.0.0.1 &
  sleep 3
done
