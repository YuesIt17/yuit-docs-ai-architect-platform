# Load testing and run captures

Reproducible load smoke results and verification captures (numbers are never invented). Formerly `docs/load-testing/`.

## Contents after a real run

| Path | Contents |
|------|------------|
| `manifest.json` | commit SHA, date, OS, providers, corpus size |
| `pytest.txt` | `pytest -q` output |
| `demo_check.json` | `scripts/demo_check.py` output |
| `load/` | raw JSON from `load_smoke.py` (MOCK + Ollama) |
| `trace.md` | Grafana Tempo: trace id + span list for one chat request |
| `loki.md` | confirmation that API logs are visible in Loki |
| `bff-overhead.md` | raw latency, memory and refresh results for the BFF |
| `manifest.template.json` | empty template with field hints |

Curated narrative: [../quality/load-report.md](../quality/load-report.md) · sizing: [../quality/capacity-planning.md](../quality/capacity-planning.md).

## How to update

```powershell
# From the repo root after hybrid-up (API on :8080 or :30080)
cd app/backend
.\.venv\Scripts\python -m pytest -q | Tee-Object -FilePath ..\..\docs\load-testing\pytest.txt

python ..\scripts\demo_check.py --base-url http://127.0.0.1:30080 `
  | Out-File -Encoding utf8 ..\..\docs\load-testing\demo_check.json

python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 20 --label mock
# With OLLAMA in Helm/API:
python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 10 --concurrency 1 --label ollama
```

Fill in `trace.md` / `loki.md` from Grafana Explore (deep links are on the Ops page). Copy `manifest.template.json` → `manifest.json` and specify the hardware (see [capacity-planning](../quality/capacity-planning.md)).

## Video

No demo video is published with this repository. Leave `video_url` empty in `manifest.json`.
