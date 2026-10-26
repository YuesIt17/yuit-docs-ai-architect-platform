# Диаграммы Knowledge Platform

| Путь | Содержимое |
|------|------------|
| [`model/`](model/) | Structurizr DSL + source-map (модель C4, не Mermaid) |
| [`sources/manual/`](sources/manual/) | Ручные Mermaid (C4 views, sequence, data-flow, ER, target) |
| [`sources/gen/`](sources/gen/) | Generated Mermaid / manifests (LangGraph, Pyreverse, Helm) |
| [`images/`](images/) | **Канонические SVG** (из `manual/` + `gen/`) |

| Диаграмма | SVG | Origin |
|-----------|-----|--------|
| C4 L1 Context | [images/c4-context.svg](images/c4-context.svg) | manual |
| C4 L2 Containers | [images/c4-container.svg](images/c4-container.svg) | manual |
| C4 L3 Components | [images/c4-backend-components.svg](images/c4-backend-components.svg) | manual |
| Hybrid deployment | [images/current-hybrid-deployment.svg](images/current-hybrid-deployment.svg) | manual |
| Sequence chat | [images/sequence-chat.svg](images/sequence-chat.svg) | manual |
| Data flow | [images/data-flow.svg](images/data-flow.svg) | manual |
| ER conceptual | [images/er-conceptual.svg](images/er-conceptual.svg) | manual |
| Target overview | [images/target-overview.svg](images/target-overview.svg) | manual |
| Agent workflow | [images/agent-workflow.svg](images/agent-workflow.svg) | gen |
| Python packages | [images/python-packages.svg](images/python-packages.svg) | gen |
| K8s topology (desktop, Mermaid) | [images/k8s-topology-desktop.svg](images/k8s-topology-desktop.svg) | gen |
| K8s topology (KubeDiagrams icons) | [images/k8s-topology-desktop-kube.svg](images/k8s-topology-desktop-kube.svg) | gen |

Сборка: [`docs/DIAGRAMS.md`](../../docs/DIAGRAMS.md)

```powershell
python tools/diagrams/build.py --profile desktop
```
