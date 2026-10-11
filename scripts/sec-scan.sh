#!/usr/bin/env bash
# DevSecOps lab: kubectl audit + Trivy images + Semgrep on backend.
# Docs: docs/infra/sec-ops.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="infra/docker-compose.sec-ops.yml"
OUT_DIR="$ROOT/tmp/sec-ops"
mkdir -p "$OUT_DIR"

echo "==> kubectl audit (namespace kp)"
AUDIT="$OUT_DIR/kubectl-audit.txt"
{
  echo "=== kubectl audit $(date -Iseconds 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo
  if command -v kubectl >/dev/null 2>&1; then
    echo "\$ kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy"
    kubectl -n kp get deploy,svc,ingress,sa,secret,networkpolicy 2>&1 || true
    echo
    echo "\$ kubectl -n kp get pods -o wide"
    kubectl -n kp get pods -o wide 2>&1 || true
    echo
    echo "\$ kubectl auth can-i --list --as=system:serviceaccount:kp:default -n kp"
    kubectl auth can-i --list --as=system:serviceaccount:kp:default -n kp 2>&1 || true
    echo
    echo "\$ kubectl auth can-i get secrets --as=system:serviceaccount:kp:default -n kp"
    kubectl auth can-i get secrets --as=system:serviceaccount:kp:default -n kp 2>&1 || true
    echo
    echo "\$ kubectl auth can-i create pods --as=system:serviceaccount:kp:default -n kp"
    kubectl auth can-i create pods --as=system:serviceaccount:kp:default -n kp 2>&1 || true
    echo
    echo "\$ kubectl -n kp get pods -o yaml | grep -E 'privileged:|hostNetwork:|hostPath:|docker.sock'"
    if kubectl -n kp get pods -o yaml 2>/dev/null | grep -E 'privileged:|hostNetwork:|hostPath:|docker.sock' | sort -u; then
      :
    else
      echo "(no matches for privileged/hostNetwork/hostPath/docker.sock)"
    fi
    echo
  else
    echo "kubectl not found — skip cluster audit"
  fi
} >"$AUDIT"
echo "    wrote $AUDIT"

echo "==> Trivy image scans"
for img in kp-api:dev kp-frontend:dev; do
  safe="${img//[:\/]/-}"
  echo "    scanning $img"
  set +e
  docker compose -f "$COMPOSE" run --rm trivy image --severity HIGH,CRITICAL -f json -o "/out/trivy-${safe}.json" "$img"
  code=$?
  set -e
  if [[ "$code" -ne 0 && "$code" -ne 1 ]]; then
    echo "WARN: trivy exit $code for $img (image missing? build via make k8s-up)" >&2
  fi
done

echo "==> Trivy config (Helm chart)"
set +e
docker compose -f "$COMPOSE" run --rm trivy config -f json -o /out/trivy-helm-config.json /src/infra/helm/knowledge-platform
code=$?
set -e
if [[ "$code" -ne 0 && "$code" -ne 1 ]]; then
  echo "WARN: trivy config exit $code" >&2
fi

echo "==> Parse Trivy CRITICAL/HIGH"
shopt -s nullglob
trivy_files=("$OUT_DIR"/trivy-*.json)
if [[ ${#trivy_files[@]} -gt 0 ]]; then
  python3 "$ROOT/scripts/sec-parse-trivy.py" "${trivy_files[@]}" || python "$ROOT/scripts/sec-parse-trivy.py" "${trivy_files[@]}"
else
  echo "WARN: no trivy JSON reports" >&2
fi

echo "==> Semgrep backend"
set +e
docker compose -f "$COMPOSE" run --rm semgrep \
  semgrep --config=auto --quiet --json -o /out/semgrep.json /src/backend
code=$?
set -e
if [[ "$code" -ne 0 && "$code" -ne 1 ]]; then
  echo "WARN: semgrep exit $code" >&2
elif [[ -f "$OUT_DIR/semgrep.json" ]]; then
  python3 -c "import json; d=json.load(open('$OUT_DIR/semgrep.json')); print(f\"    semgrep findings: {len(d.get('results',[]))}  ($OUT_DIR/semgrep.json)\")" 2>/dev/null \
    || echo "    wrote $OUT_DIR/semgrep.json"
fi

echo
echo "Done. Reports: tmp/sec-ops/"
echo "Guide: docs/infra/sec-ops.md"
