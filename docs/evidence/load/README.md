# Raw Load Smoke Results

| File | Provider | Notes |
| ---- | -------- | ------- |
| `smoke_mock_20x1.json` | MOCK | Local uvicorn `:8080` |
| `smoke_ollama_10x1.json` | OLLAMA | `load_smoke` 10×1 hybrid (success 50%, ~16 min) |
| `smoke_ollama_7x1.json` | OLLAMA | Additional `/v1/audit` latency samples |
| `last_run.md` | — | Fragment from `load_smoke.py --write-report-fragment` |

```powershell
python app/backend/scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 3 --label ollama --timeout 90 --write-report-fragment
```

If Ollama runs away on long generation: `docker restart retailpartnerx-kp-ollama-1`, then resample from audit or with fewer requests.

The JSON files are unmodified captures, so they contain the test questions exactly as they were used at the time.
