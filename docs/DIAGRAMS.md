# Architecture from Code (diagrams-as-code)

A reproducible pipeline: **implementation sources → facts / model → SVG**.
Diagrams do **not** prove the security or health of a live cluster.

## Bootstrap (once)

Requirements: Docker Desktop (Structurizr CLI), Node.js/npm (Mermaid CLI), the backend Python venv, Helm, Graphviz (`dot`).

```powershell
python tools/diagrams/build.py --bootstrap
```

Pinned versions: [`tools/diagrams/tools.lock`](../tools/diagrams/tools.lock), `package-lock.json`, `requirements.txt`.

## Build / check

```powershell
python tools/diagrams/build.py --profile desktop
python tools/diagrams/build.py --profile desktop --check
```

or `make diagrams` / `make diagrams-check`.

`--check` regenerates `sources/gen/` into a temporary directory and compares it with the committed gen + inventory. It does **not** overwrite artifacts. Manual `.mmd` files are not regenerated.

The **`gpu`** profile is pending (there is no `values-gpu.yaml`), so the build refuses to fabricate manifests.

## Where to edit what

| What | Edit | Generated? |
|------|------|------------|
| C4 DSL (validate) | [`architecture/diagrams/model/workspace.dsl`](../architecture/diagrams/model/workspace.dsl) | no |
| C4 / hybrid / target Mermaid | [`architecture/diagrams/sources/manual/`](../architecture/diagrams/sources/manual/) | SVG only |
| Source mapping | [`architecture/diagrams/model/source-map.yaml`](../architecture/diagrams/model/source-map.yaml) | no (checked) |
| Sequence / data-flow / ER | [`architecture/diagrams/sources/manual/`](../architecture/diagrams/sources/manual/) | SVG only |
| Agent workflow | code in [`kp/agent/graph.py`](../app/backend/kp/agent/graph.py) | `sources/gen/agent-workflow.*` |
| Python code view | `kp.*` packages | Pyreverse → `sources/gen/` |
| K8s topology | Helm values + templates | helm template → `sources/gen/` |

Canonical artifacts: [`architecture/diagrams/images/*.svg`](../architecture/diagrams/images/).

## Provenance levels

1. **generated-from-code** (`sources/gen/`): LangGraph, Pyreverse, Helm→KubeDiagrams  
2. **curated-from-code** (`sources/manual/`): C4 Mermaid, sequence, data-flow (with source-map)  
3. **target-design** (`sources/manual/`): IdP/Vault/vLLM/OCR overview, ER from `init.sql` (intended)

## Profiles

| Profile | Inputs | Notes |
|---------|--------|-------|
| desktop | `values.yaml` + `values-desktop.yaml` | default CI |
| gpu | — | **pending** |

Compose Ollama/obs appear in the hybrid deployment (manual Mermaid + Structurizr DSL), not in KubeDiagrams.

## Offline

After bootstrap, the build needs no cloud API, live cluster, GPU or production credentials.
Mermaid `securityLevel: loose` applies only to locally trusted `.mmd` files.
Secret/stringData values in manifests are replaced with fixture values before KubeDiagrams/inventory.

## Editor preview

Cursor/VS Code Mermaid preview mostly understands `flowchart` / `graph` / `stateDiagram`.
Committed `.mmd` files use **flowchart TB**; `mmdc` builds the SVGs with `layout: elk` ([`tools/diagrams/mermaid-config.json`](../tools/diagrams/mermaid-config.json)) so the layout matches the preview (siblings on one rank) rather than the default dagre.
The Structurizr DSL (`model/workspace.dsl`) is the C4 model for `validate`; SVGs render from `sources/manual/` + `sources/gen/` (not from the Structurizr Mermaid export with `<div>`).
The SVG theme is `neutral` with a white background (for README/print); the preview in dark Cursor looks darker, but the graph is the same.

## Drift

If `diagrams-check` fails:

1. Confirm that the code/Helm change is intentional.  
2. `python tools/diagrams/build.py --profile desktop`  
3. Commit the updated `architecture/diagrams/sources/gen/**` and SVGs (except the SHA loop in provenance: the git SHA is included only with `DIAGRAMS_INCLUDE_GIT_SHA=1` in CI artifacts).

## Adding a view

1. Add a view to `architecture/diagrams/model/workspace.dsl` **or** an `.mmd` file to `architecture/diagrams/sources/manual/`.  
2. Bind the symbols in `source-map.yaml`.  
3. Extend `check_consistency.check_expected_outputs` if needed.  
4. Rebuild and commit the SVGs.

## Limitations

- The Structurizr Mermaid export is not the native Structurizr renderer.  
- Pyreverse is static analysis; DI/duck typing are incomplete.  
- KubeDiagrams shows the **declared** topology from `helm template`, not a live cluster.  
- Postgres holds dialog checkpoints; audit and inline jobs are in-memory.  
- OCR: MOCK by default, RapidOCR when enabled.
