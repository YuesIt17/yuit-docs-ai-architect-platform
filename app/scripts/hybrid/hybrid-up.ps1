# Clean hybrid: Compose side-stack (Ollama + obs) + Desktop K8s platform (no service overlap).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $Root

Write-Host "==> Compose side-stack (ollama + prometheus/grafana/tempo/loki)"
docker compose -f app/infra/docker-compose.yml --profile llm --profile obs up -d --remove-orphans
& "$Root\app\scripts\ollama\ollama-pull.ps1" -Model "qwen2.5:0.5b"

Write-Host "==> Kubernetes platform (api/frontend/stores/minio) + OLLAMA overlay"
$env:KP_LLM = "compose-ollama"
& "$Root\app\scripts\k8s\k8s-up.ps1"

Write-Host @"

Hybrid ready (no Compose↔K8s duplicates):
  UI     http://kp.local:8088
  API    http://kp.local:8088/api/health
  Ollama http://127.0.0.1:11434/v1/models
  Graf   http://127.0.0.1:3000  (Explore: Tempo + Loki)
  Prom   http://127.0.0.1:9090
  Tempo  http://127.0.0.1:3200
  Loki   http://127.0.0.1:3100
"@
