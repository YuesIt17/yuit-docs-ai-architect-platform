# Agent Guide

Rules for coding agents. It covers only what the code does not show. For an overview, see [`README.md`](README.md).

## Project rules

- All project text is English: UI, docs, code, comments, commit messages. This repository is a public portfolio.
- Cyrillic is allowed only in the RusLawOD status match in `app/backend/pipelines/ingest_ruslaw.py`, because removing it would ingest classified acts as public, and in raw captures under `docs/evidence/load/`.
- Claim only what was run. Label the rest as "not verified", as the README does for the vLLM GPU runtime. Do not raise a status without evidence.
- `sources/gen`, `images`, `inventory.json` and `provenance.json` under `architecture/diagrams/` are generated. Do not edit them by hand.

## Commands

Run from `app/backend`, using `.venv/bin/python` on macOS and Linux:

```bash
OTEL_SDK_DISABLED=true .venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m evals.run_eval --report eval-report.json
```

Run from the repository root, with `PYTHONPATH=tools/diagrams:app/backend` (`;` as the separator on Windows):

```bash
app/backend/.venv/Scripts/python.exe -m pytest -q tests/architecture
```

## Environment traps

- The local venv may run a newer Python than CI and the Docker images, which use 3.12. If a dependency does not install locally, check it on 3.12 before changing the design. Ragas does not build on 3.14.
- `app/backend/Dockerfile` lists dependencies by hand. When you add a runtime dependency to `pyproject.toml`, add it there too.
- On Windows, a system proxy can break `kubectl`. Add `kubernetes.docker.internal` to `NO_PROXY`.
- Docker Desktop `hostpath` volumes ignore `fsGroup`, and its CNI does not enforce NetworkPolicy. See [`docs/infra/k8s-hardening.md`](docs/infra/k8s-hardening.md).

## When you change these

| Change | Also do |
| ------ | ------- |
| `kp/agent/graph.py` or the Helm chart | Rebuild the diagrams, or the `diagrams` workflow fails on drift. See [`docs/DIAGRAMS.md`](docs/DIAGRAMS.md) |
| Helm security settings | Run `tests/architecture` and update `docs/infra/k8s-hardening.md` |
| Retrieval, routing or the answer flow | Run the eval gate. See [`docs/evaluation.md`](docs/evaluation.md) |
| Python code or tests | Run ruff and pytest |
| `app/bff` | Run `go vet`, `go test -race` and `golangci-lint`. See [`app/bff/README.md`](app/bff/README.md) |

## Git

- Work on a branch and merge through a pull request. Do not commit to `main`.
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.
- Keep local notes and scratch files in `tmp/`, which is ignored.
- The repository is public. Do not commit real credentials. Credentials in the chart and compose files are local demo values.
