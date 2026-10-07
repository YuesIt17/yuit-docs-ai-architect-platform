# Диаграммы Knowledge Platform

Схемы сдачи (Draw.io + PNG). Specs для перегенерации: [`_dev/specs/`](_dev/specs/).

| Диаграмма | PNG | Draw.io |
| --------- | --- | ------- |
| C4 L1 Контекст | [c4-context.png](c4-context.png) | [c4-context.drawio](c4-context.drawio) |
| C4 L2 Контейнеры | [c4-container.png](c4-container.png) | [c4-container.drawio](c4-container.drawio) |
| C4 L3 Компоненты агента | [c4-component.png](c4-component.png) | [c4-component.drawio](c4-component.drawio) |
| Deployment | [deployment.png](deployment.png) | [deployment.drawio](deployment.drawio) |
| Sequence (chat) | [sequence-chat.png](sequence-chat.png) | [sequence-chat.drawio](sequence-chat.drawio) |
| ER | [er-diagram.png](er-diagram.png) | [er-diagram.drawio](er-diagram.drawio) |
| Data Flow | [data-flow.png](data-flow.png) | [data-flow.drawio](data-flow.drawio) |
| Compose topology | [compose-topology.png](compose-topology.png) | [compose-topology.drawio](compose-topology.drawio) |
| K8s topology | [k8s-topology.png](k8s-topology.png) | [k8s-topology.drawio](k8s-topology.drawio) |

Markdown + Mermaid: [`docs/architecture/`](../docs/architecture/) · infra: [`docs/infra/`](../docs/infra/).

Перегенерация (из `yuit-docs-ai-architect/tools/drawio-mcp`):

```powershell
node src/cli.mjs --spec <platform>/diagrams/_dev/specs/c4-context.json --output <platform>/diagrams/c4-context.drawio
node src/cli.mjs --export-png <platform>/diagrams/c4-context.drawio --spec-path <platform>/diagrams/_dev/specs/c4-context.json
```

Fallback PNG для compose/k8s topology (если drawio CLI / Docker недоступны):

```powershell
python diagrams/_dev/render_topology_png.py
```
