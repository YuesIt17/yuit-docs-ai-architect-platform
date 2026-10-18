#!/usr/bin/env bash
# DevSecOps lab: kubectl + Trivy + Semgrep + Checkov + Nmap + Nuclei (+ ZAP if SEC_SCAN_DEEP=1).
# Docs: docs/infra/sec-ops.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

COMPOSE="app/infra/docker-compose.sec-ops.yml"
OUT_DIR="$ROOT/tmp/sec-ops"
mkdir -p "$OUT_DIR"
DEEP="${SEC_SCAN_DEEP:-0}"

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
  python3 "$ROOT/app/scripts/sec/sec-parse-trivy.py" "${trivy_files[@]}" || python "$ROOT/app/scripts/sec/sec-parse-trivy.py" "${trivy_files[@]}"
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

echo "==> Checkov (Helm chart)"
set +e
docker compose -f "$COMPOSE" run --rm checkov \
  -d /src/infra/helm/knowledge-platform \
  --framework kubernetes helm --soft-fail \
  -o json --output-file-path /out
code=$?
set -e
if [[ "$code" -ne 0 && "$code" -ne 1 ]]; then
  echo "WARN: checkov exit $code" >&2
fi
# Normalize Checkov output name
if [[ -f "$OUT_DIR/results_json.json" && ! -f "$OUT_DIR/checkov.json" ]]; then
  mv "$OUT_DIR/results_json.json" "$OUT_DIR/checkov.json"
  echo "    wrote $OUT_DIR/checkov.json"
elif [[ -f "$OUT_DIR/checkov.json" ]]; then
  echo "    wrote $OUT_DIR/checkov.json"
elif [[ -f "$OUT_DIR/results_json.json" ]]; then
  cp "$OUT_DIR/results_json.json" "$OUT_DIR/checkov.json"
  echo "    wrote $OUT_DIR/checkov.json"
fi

echo "==> Nmap (host.docker.internal — local Ingress only)"
set +e
docker compose -f "$COMPOSE" run --rm nmap \
  -sV -p 8088,80,443,11434 -oN /out/nmap.txt host.docker.internal
code=$?
set -e
if [[ "$code" -ne 0 && "$code" -ne 1 ]]; then
  echo "WARN: nmap exit $code" >&2
else
  echo "    wrote $OUT_DIR/nmap.txt"
fi

echo "==> Nuclei (http://host.docker.internal:8088)"
set +e
docker compose -f "$COMPOSE" run --rm nuclei \
  -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
code=$?
set -e
if [[ "$code" -ne 0 && "$code" -ne 1 && "$code" -ne 2 ]]; then
  echo "WARN: nuclei exit $code (is Ingress up on :8088?)" >&2
else
  echo "    wrote $OUT_DIR/nuclei.txt"
fi

echo "==> kube-bench (best-effort)"
set +e
docker compose -f "$COMPOSE" run --rm kube-bench \
  run --targets policies >"$OUT_DIR/kube-bench.txt" 2>&1
code=$?
set -e
if [[ "$code" -ne 0 ]]; then
  echo "WARN: kube-bench exit $code — often unsupported on Docker Desktop; see tmp/sec-ops/kube-bench.txt" >&2
else
  echo "    wrote $OUT_DIR/kube-bench.txt"
fi

if [[ "$DEEP" == "1" || "$DEEP" == "true" || "$DEEP" == "yes" ]]; then
  echo "==> ZAP baseline (SEC_SCAN_DEEP=$DEEP)"
  set +e
  docker compose -f "$COMPOSE" run --rm zap \
    zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
  code=$?
  set -e
  if [[ "$code" -gt 3 ]]; then
    echo "WARN: zap exit $code" >&2
  else
    echo "    wrote $OUT_DIR/zap-baseline.json (zap exit $code; 0-3 often OK with findings)"
  fi
else
  echo "==> ZAP skipped (set SEC_SCAN_DEEP=1 for baseline)"
fi

echo "==> Summary"
python3 "$ROOT/app/scripts/sec/sec-parse-summary.py" "$OUT_DIR" 2>/dev/null \
  || python "$ROOT/app/scripts/sec/sec-parse-summary.py" "$OUT_DIR" 2>/dev/null \
  || echo "WARN: sec-parse-summary.py failed" >&2

echo
echo "Done. Reports: tmp/sec-ops/"
echo "Guide: docs/infra/sec-ops.md"
