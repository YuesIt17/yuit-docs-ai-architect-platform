# Диаграммы Knowledge Platform

Всё в одном каталоге:

| Путь | Содержимое |
|------|------------|
| [`model/`](model/) | Structurizr DSL + source-map + Mermaid fallbacks |
| [`curated/`](curated/) | Ручные sequence / data-flow / ER (не выдавать за codegen) |
| [`sources/`](sources/) | Generated Mermaid (LangGraph, Structurizr export, Pyreverse, …) |
| [`images/`](images/) | **Канонические SVG** |

| Диаграмма | SVG |
|-----------|-----|
| C4 L1 Context | [images/c4-context.svg](images/c4-context.svg) |
| C4 L2 Containers | [images/c4-container.svg](images/c4-container.svg) |
| C4 L3 Components | [images/c4-backend-components.svg](images/c4-backend-components.svg) |
| Hybrid deployment | [images/current-hybrid-deployment.svg](images/current-hybrid-deployment.svg) |
| Agent workflow | [images/agent-workflow.svg](images/agent-workflow.svg) |
| Python packages | [images/python-packages.svg](images/python-packages.svg) |
| K8s topology (desktop, Mermaid) | [images/k8s-topology-desktop.svg](images/k8s-topology-desktop.svg) |
| K8s topology (KubeDiagrams icons) | [images/k8s-topology-desktop-kube.svg](images/k8s-topology-desktop-kube.svg) |
| Sequence chat | [images/sequence-chat.svg](images/sequence-chat.svg) |
| Data flow | [images/data-flow.svg](images/data-flow.svg) |
| ER conceptual | [images/er-conceptual.svg](images/er-conceptual.svg) |
| Target overview | [images/target-overview.svg](images/target-overview.svg) |

Сборка: [`docs/DIAGRAMS.md`](../../docs/DIAGRAMS.md)

```powershell
python tools/diagrams/build.py --profile desktop
```
