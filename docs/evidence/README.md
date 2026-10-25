# Evidence folder

Place reproducible check outputs here (do not invent numbers or screenshots).

Suggested layout after a real run:

| Path | Content |
|------|---------|
| `manifest.json` | commit SHA, date, OS, providers, corpus size |
| `pytest.txt` | `pytest -q` output |
| `demo_check.json` | output of `scripts/demo_check.py` |
| `load/` | raw JSON from load_smoke scenarios |
| `trace.md` | Grafana Tempo trace id + span list for one chat request |
| `loki.md` | confirmation that API pod/container logs appear in Loki (not only Docker socket narrative) |

Video recording: **pending** (owner records later). Do not add a fake URL.
