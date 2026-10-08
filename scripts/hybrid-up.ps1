# Clean hybrid: Compose side-stack (Ollama + obs) + Desktop K8s platform (no service overlap).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Compose side-stack (ollama + prometheus/grafana/jaeger)"
docker compose -f infra/docker-compose.yml --profile llm --profile obs up -d --remove-orphans
& "$Root\scripts\ollama-pull.ps1" -Model "qwen2.5:0.5b"

Write-Host "==> Kubernetes platform (api/frontend/stores/minio) + OLLAMA overlay"
$env:KP_LLM = "compose-ollama"
& "$Root\scripts\k8s-up.ps1"

Write-Host @"

Hybrid ready (no Compose↔K8s duplicates):
  UI     http://kp.local:8088
  API    http://kp.local:8088/api/health
  Ollama http://127.0.0.1:11434/v1/models
  Jaeger http://127.0.0.1:16686
  Prom   http://127.0.0.1:9090
  Graf   http://127.0.0.1:3000

Do NOT run make demo-standalone while K8s is up.
"@
