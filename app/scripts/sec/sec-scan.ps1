# DevSecOps lab: kubectl + Trivy + Semgrep + Checkov + Nmap + Nuclei (+ ZAP if SEC_SCAN_DEEP=1).
# Requires: docker, kubectl. Prefer after `make demo` / `make k8s-up`.
# Docs: docs/infra/sec-ops.md

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
Set-Location $Root

$Compose = "app/infra/docker-compose.sec-ops.yml"
$OutDir = Join-Path $Root "tmp\sec-ops"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$Deep = $env:SEC_SCAN_DEEP

Write-Host "==> kubectl audit (namespace kp)"
$audit = Join-Path $OutDir "kubectl-audit.txt"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("=== kubectl audit $(Get-Date -Format o) ===")
$lines.Add("")

function Invoke-KubectlCapture([string[]]$KubectlArgs) {
  $cmd = "kubectl " + ($KubectlArgs -join " ")
  $lines.Add("`$ $cmd")
  try {
    $out = & kubectl @KubectlArgs 2>&1 | Out-String
    $lines.Add($out.TrimEnd())
  } catch {
    $lines.Add("(kubectl failed: $($_.Exception.Message))")
  }
  $lines.Add("")
}

if (Get-Command kubectl -ErrorAction SilentlyContinue) {
  Invoke-KubectlCapture @("-n", "kp", "get", "deploy,svc,ingress,sa,secret,networkpolicy")
  Invoke-KubectlCapture @("-n", "kp", "get", "pods", "-o", "wide")
  Invoke-KubectlCapture @("auth", "can-i", "--list", "--as=system:serviceaccount:kp:default", "-n", "kp")
  Invoke-KubectlCapture @("auth", "can-i", "get", "secrets", "--as=system:serviceaccount:kp:default", "-n", "kp")
  Invoke-KubectlCapture @("auth", "can-i", "create", "pods", "--as=system:serviceaccount:kp:default", "-n", "kp")

  $lines.Add("`$ kubectl -n kp get pods -o yaml | Select-String privileged|hostNetwork|hostPath|docker.sock")
  try {
    $yaml = kubectl -n kp get pods -o yaml 2>&1 | Out-String
    $hits = $yaml | Select-String -Pattern "privileged:|hostNetwork:|hostPath:|docker.sock" -AllMatches
    if ($hits) {
      $lines.Add(($hits | ForEach-Object { $_.Line.Trim() } | Select-Object -Unique) -join "`n")
    } else {
      $lines.Add("(no matches for privileged/hostNetwork/hostPath/docker.sock)")
    }
  } catch {
    $lines.Add("(pod yaml scan failed - is namespace kp up?)")
  }
  $lines.Add("")
} else {
  $lines.Add("kubectl not found - skip cluster audit")
  Write-Host "WARN: kubectl not found; skipping cluster audit" -ForegroundColor Yellow
}

$lines | Set-Content -Path $audit -Encoding utf8
Write-Host "    wrote $audit"

Write-Host "==> Trivy image scans"
$images = @("kp-api:dev", "kp-frontend:dev")
foreach ($img in $images) {
  $safe = $img -replace "[:/]", "-"
  $jsonOut = "/out/trivy-$safe.json"
  Write-Host "    scanning $img"
  docker compose -f $Compose run --rm trivy image --severity HIGH,CRITICAL -f json -o $jsonOut $img
  if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
    Write-Host "WARN: trivy exit $LASTEXITCODE for $img (image missing? build via make k8s-up)" -ForegroundColor Yellow
  }
}

Write-Host "==> Trivy config (Helm chart)"
docker compose -f $Compose run --rm trivy config -f json -o /out/trivy-helm-config.json /src/infra/helm/knowledge-platform
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: trivy config exit $LASTEXITCODE" -ForegroundColor Yellow
}

Write-Host "==> Parse Trivy CRITICAL/HIGH"
$trivyFiles = Get-ChildItem -Path $OutDir -Filter "trivy-*.json" -ErrorAction SilentlyContinue
if ($trivyFiles) {
  python (Join-Path $Root "app\scripts\sec\sec-parse-trivy.py") @($trivyFiles.FullName)
} else {
  Write-Host "WARN: no trivy JSON reports" -ForegroundColor Yellow
}

Write-Host "==> Semgrep backend"
docker compose -f $Compose run --rm semgrep `
  semgrep --config=auto --quiet --json -o /out/semgrep.json /src/backend
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: semgrep exit $LASTEXITCODE" -ForegroundColor Yellow
} else {
  $sg = Join-Path $OutDir "semgrep.json"
  if (Test-Path $sg) {
    try {
      $data = Get-Content $sg -Raw | ConvertFrom-Json
      $n = @($data.results).Count
      Write-Host "    semgrep findings: $n  ($sg)"
    } catch {
      Write-Host "    wrote $sg"
    }
  }
}

Write-Host "==> Checkov (Helm chart)"
docker compose -f $Compose run --rm checkov `
  -d /src/infra/helm/knowledge-platform `
  --framework kubernetes helm --soft-fail `
  -o json --output-file-path /out
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: checkov exit $LASTEXITCODE" -ForegroundColor Yellow
}
$resultsJson = Join-Path $OutDir "results_json.json"
$checkovJson = Join-Path $OutDir "checkov.json"
if ((Test-Path $resultsJson) -and -not (Test-Path $checkovJson)) {
  Move-Item -Force $resultsJson $checkovJson
  Write-Host "    wrote $checkovJson"
} elseif (Test-Path $resultsJson) {
  Copy-Item -Force $resultsJson $checkovJson
  Write-Host "    wrote $checkovJson"
} elseif (Test-Path $checkovJson) {
  Write-Host "    wrote $checkovJson"
}

Write-Host "==> Nmap (host.docker.internal — local Ingress only)"
docker compose -f $Compose run --rm nmap `
  -sV -p 8088,80,443,11434 -oN /out/nmap.txt host.docker.internal
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
  Write-Host "WARN: nmap exit $LASTEXITCODE" -ForegroundColor Yellow
} else {
  Write-Host "    wrote $(Join-Path $OutDir 'nmap.txt')"
}

Write-Host "==> Nuclei (http://host.docker.internal:8088)"
docker compose -f $Compose run --rm nuclei `
  -u http://host.docker.internal:8088 -silent -o /out/nuclei.txt
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1 -and $LASTEXITCODE -ne 2) {
  Write-Host "WARN: nuclei exit $LASTEXITCODE (is Ingress up on :8088?)" -ForegroundColor Yellow
} else {
  Write-Host "    wrote $(Join-Path $OutDir 'nuclei.txt')"
}

Write-Host "==> kube-bench (best-effort)"
$kbOut = Join-Path $OutDir "kube-bench.txt"
try {
  docker compose -f $Compose run --rm kube-bench run --targets policies 2>&1 | Out-File -FilePath $kbOut -Encoding utf8
  if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: kube-bench exit $LASTEXITCODE — often unsupported on Docker Desktop; see tmp/sec-ops/kube-bench.txt" -ForegroundColor Yellow
  } else {
    Write-Host "    wrote $kbOut"
  }
} catch {
  "kube-bench failed: $($_.Exception.Message)" | Set-Content -Path $kbOut -Encoding utf8
  Write-Host "WARN: kube-bench failed — see tmp/sec-ops/kube-bench.txt" -ForegroundColor Yellow
}

if ($Deep -eq "1" -or $Deep -eq "true" -or $Deep -eq "yes") {
  Write-Host "==> ZAP baseline (SEC_SCAN_DEEP=$Deep)"
  docker compose -f $Compose run --rm zap `
    zap-baseline.py -t http://host.docker.internal:8088 -J /out/zap-baseline.json -I
  if ($LASTEXITCODE -gt 3) {
    Write-Host "WARN: zap exit $LASTEXITCODE" -ForegroundColor Yellow
  } else {
    Write-Host "    wrote $(Join-Path $OutDir 'zap-baseline.json') (zap exit $LASTEXITCODE; 0-3 often OK with findings)"
  }
} else {
  Write-Host "==> ZAP skipped (set SEC_SCAN_DEEP=1 for baseline)"
}

Write-Host "==> Summary"
try {
  python (Join-Path $Root "app\scripts\sec\sec-parse-summary.py") $OutDir
} catch {
  Write-Host "WARN: sec-parse-summary.py failed" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Reports: tmp/sec-ops/"
Write-Host "Guide: docs/infra/sec-ops.md"
