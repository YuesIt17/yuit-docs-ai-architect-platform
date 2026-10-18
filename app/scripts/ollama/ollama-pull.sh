#!/usr/bin/env bash
# Pull an Ollama model (macOS / Linux). Windows: app/scripts/ollama/ollama-pull.ps1
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

MODEL="${1:-qwen2.5:0.5b}"
COMPOSE_FILE="${COMPOSE_FILE:-app/infra/docker-compose.yml}"
RETRIES="${RETRIES:-12}"

echo "==> Ensuring ollama container (profile llm)"
docker compose -f "$COMPOSE_FILE" --profile llm up -d ollama

cid="$(docker ps -qf name=ollama | head -n1 || true)"
if [[ -z "$cid" ]]; then
  echo "ERROR: ollama container not running" >&2
  exit 1
fi

echo "==> Pulling model: $MODEL (retries=$RETRIES)"
n=0
until docker exec "$cid" ollama pull "$MODEL"; do
  n=$((n + 1))
  if [[ "$n" -ge "$RETRIES" ]]; then
    echo "ERROR: ollama pull failed after $RETRIES attempts" >&2
    exit 1
  fi
  echo "    retry $n/$RETRIES in 5s..."
  sleep 5
done

echo "Done. Models: curl -s http://127.0.0.1:11434/v1/models"
