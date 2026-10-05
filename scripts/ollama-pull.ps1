<#
.SYNOPSIS
  Pull an Ollama model with retries / alternate DNS (fixes TLS timeouts to registry.ollama.ai).

.USAGE
  .\scripts\ollama-pull.ps1
  .\scripts\ollama-pull.ps1 -Model qwen2.5:1.5b-instruct
  .\scripts\ollama-pull.ps1 -Model qwen2.5:7b-instruct -Retries 15
#>
param(
  [string]$Model = "qwen2.5:1.5b-instruct",
  [int]$Retries = 12,
  [string]$ComposeFile = "infra/docker-compose.yml"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-OllamaContainer {
  $id = docker ps -qf "name=ollama" 2>$null | Select-Object -First 1
  if (-not $id) { return $null }
  return $id
}

Write-Host "==> Ensuring ollama container (profile llm, DNS 8.8.8.8/1.1.1.1)"
docker compose -f $ComposeFile --profile llm up -d ollama
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: docker compose failed (is Docker Desktop running?)"
  exit 1
}

$cid = Get-OllamaContainer
if (-not $cid) {
  Write-Host "ERROR: ollama container not running"
  exit 1
}

Write-Host "==> Probe registry from host"
curl.exe -sS -m 15 -o NUL -w "registry HTTP %{http_code}`n" https://registry.ollama.ai/v2/
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARN: host cannot reach registry.ollama.ai - pull may fail until network/VPN/proxy is fixed"
}

Write-Host "==> Pull $Model (retries=$Retries)"
$ok = $false
for ($i = 1; $i -le $Retries; $i++) {
  $cid = Get-OllamaContainer
  if (-not $cid) {
    docker compose -f $ComposeFile --profile llm up -d ollama | Out-Null
    $cid = Get-OllamaContainer
  }
  Write-Host "--- attempt $i/$Retries (container $cid) ---"
  docker exec $cid ollama pull $Model
  if ($LASTEXITCODE -eq 0) {
    $ok = $true
    break
  }
  $sleep = [Math]::Min(120, 10 * $i)
  Write-Host "pull failed; sleeping ${sleep}s"
  Start-Sleep $sleep
}

if (-not $ok) {
  Write-Host ""
  Write-Host "FAILED to pull $Model after $Retries attempts."
  Write-Host "Offline / alternate options:"
  Write-Host "  1) Fix TLS/VPN/proxy to registry.ollama.ai, then re-run this script"
  Write-Host "  2) On a machine with the model: ollama pull $Model"
  Write-Host "     then copy ~/.ollama/models into the compose volume ollama_data"
  Write-Host "  3) Keep LLM_PROVIDER=MOCK (default) - platform works without a local model"
  exit 1
}

Write-Host "==> Models available:"
docker exec (Get-OllamaContainer) ollama list
Write-Host ""
Write-Host "Done. In UI /llm:"
Write-Host "  Provider: OLLAMA"
Write-Host "  Base URL (API in compose): http://ollama:11434/v1"
Write-Host "  Base URL (API on host):    http://localhost:11434/v1"
Write-Host "  Model: $Model"
