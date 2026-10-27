# Архитектура из кода (diagrams-as-code)

Воспроизводимый pipeline: **источники реализации → факты / модель → SVG**.
Диаграммы **не** доказывают безопасность или работоспособность live-кластера.

## Bootstrap (один раз)

Требования: Docker Desktop (Structurizr CLI), Node.js/npm (Mermaid CLI), Python venv backend, Helm, Graphviz (`dot`).

```powershell
python tools/diagrams/build.py --bootstrap
```

Закреплённые версии: [`tools/diagrams/tools.lock`](../tools/diagrams/tools.lock), `package-lock.json`, `requirements.txt`.

## Build / check

```powershell
python tools/diagrams/build.py --profile desktop
python tools/diagrams/build.py --profile desktop --check
```

или `make diagrams` / `make diagrams-check`.

`--check` регенерирует `sources/gen/` во временный каталог, сравнивает с committed gen + inventory, **не** перезаписывает artifacts. Manual `.mmd` не регенерируются.

Профиль **`gpu`**: pending (нет `values-gpu.yaml`) — сборка отказывается фабриковать manifests.

## Где что править

| Что | Редактировать | Generated? |
|-----|---------------|------------|
| C4 DSL (validate) | [`architecture/diagrams/model/workspace.dsl`](../architecture/diagrams/model/workspace.dsl) | нет |
| C4 / hybrid / target Mermaid | [`architecture/diagrams/sources/manual/`](../architecture/diagrams/sources/manual/) | SVG only |
| Source mapping | [`architecture/diagrams/model/source-map.yaml`](../architecture/diagrams/model/source-map.yaml) | нет (checked) |
| Sequence / data-flow / ER | [`architecture/diagrams/sources/manual/`](../architecture/diagrams/sources/manual/) | SVG only |
| Agent workflow | код [`kp/agent/graph.py`](../app/backend/kp/agent/graph.py) | `sources/gen/agent-workflow.*` |
| Python code view | пакеты `kp.*` | Pyreverse → `sources/gen/` |
| K8s topology | Helm values + templates | helm template → `sources/gen/` |

Канонические артефакты: [`architecture/diagrams/images/*.svg`](../architecture/diagrams/images/).

## Уровни происхождения

1. **generated-from-code** (`sources/gen/`) — LangGraph, Pyreverse, Helm→KubeDiagrams  
2. **curated-from-code** (`sources/manual/`) — C4 Mermaid, sequence, data-flow (с source-map)  
3. **target-design** (`sources/manual/`) — IdP/Vault/vLLM/OCR overview, ER из `init.sql` (intended)

## Profiles

| Profile | Inputs | Notes |
|---------|--------|-------|
| desktop | `values.yaml` + `values-desktop.yaml` | default CI |
| gpu | — | **pending** |

Compose Ollama/obs отражаются в hybrid deployment (manual Mermaid + Structurizr DSL), не в KubeDiagrams.

## Offline

После bootstrap сборка не требует cloud API / живого кластера / GPU / production credentials.
Mermaid `securityLevel: loose` только для локально доверенных `.mmd`.
Secret/stringData в manifests заменяются fixture-значениями до KubeDiagrams/inventory.

## Preview в редакторе

Cursor/VS Code Mermaid preview понимает в основном `flowchart` / `graph` / `stateDiagram`.
Committed `.mmd` — **flowchart TB**; SVG собирает `mmdc` с `layout: elk` ([`tools/diagrams/mermaid-config.json`](../tools/diagrams/mermaid-config.json)), чтобы раскладка совпадала с preview (siblings на одном ранге), а не с дефолтным dagre.
Structurizr DSL (`model/workspace.dsl`) — модель C4 для `validate`; рендер SVG — из `sources/manual/` + `sources/gen/` (не из Structurizr Mermaid export с `<div>`).
Тема SVG — `neutral` + белый фон (для README/печати); preview в тёмном Cursor визуально темнее, граф тот же.

## Drift

Если `diagrams-check` падает:

1. Убедиться, что изменение кода/Helm осознанное.  
2. `python tools/diagrams/build.py --profile desktop`  
3. Закоммитить обновлённые `architecture/diagrams/sources/gen/**` и SVG (кроме SHA-loop в provenance — git SHA только при `DIAGRAMS_INCLUDE_GIT_SHA=1` в CI artifacts).

## Добавить view

1. Добавить view в `architecture/diagrams/model/workspace.dsl` **или** `.mmd` в `architecture/diagrams/sources/manual/`.  
2. Привязать символы в `source-map.yaml`.  
3. Расширить `check_consistency.check_expected_outputs` при необходимости.  
4. Пересобрать и закоммитить SVG.

## Ограничения

- Structurizr Mermaid export ≠ native Structurizr renderer.  
- Pyreverse — статический анализ; DI/duck typing неполны.  
- KubeDiagrams — **declared** topology из `helm template`, не live cluster.  
- Postgres: **deployed-unused**; audit/jobs in-memory.  
- OCR: MOCK/planned.
