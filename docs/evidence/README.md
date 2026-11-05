# Evidence Folder

This folder holds reproducible verification results (numbers and screenshots are never invented).

## Contents after a real run

| Path | Contents |
|------|------------|
| `manifest.json` | commit SHA, date, OS, providers, corpus size |
| `pytest.txt` | `pytest -q` output |
| `demo_check.json` | `scripts/demo_check.py` output |
| `load/` | raw JSON from `load_smoke.py` (MOCK + Ollama) |
| `trace.md` | Grafana Tempo: trace id + span list for one chat request |
| `loki.md` | confirmation that API logs are visible in Loki |
| `manifest.template.json` | empty template with field hints |

## How to update

```powershell
# From the repo root after hybrid-up (API on :8080 or :30080)
cd app/backend
.\.venv\Scripts\python -m pytest -q | Tee-Object -FilePath ..\..\docs\evidence\pytest.txt

python ..\scripts\demo_check.py --base-url http://127.0.0.1:30080 `
  | Out-File -Encoding utf8 ..\..\docs\evidence\demo_check.json

python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 20 --label mock
# With OLLAMA in Helm/API:
python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 10 --concurrency 1 --label ollama
```

Fill in `trace.md` / `loki.md` from Grafana Explore (deep links are on the Ops page). Copy `manifest.template.json` → `manifest.json` and specify the hardware (examples are in the template comments / capacity-planning).

## Video recording checklist

1. Keep the video to 5–7 minutes.
2. Do **not** commit the video binary.
3. After uploading, set `video_url` in `manifest.json`.
4. Screens: Chat ACL, Graph SVG + Neo4j Browser, Tempo spans, Loki logs, Grafana KP Overview.

Video recording: [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU) · `video_url` in `manifest.json`.
