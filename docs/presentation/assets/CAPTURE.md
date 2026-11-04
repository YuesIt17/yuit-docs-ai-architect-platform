# Screenshots for the Defense Deck

Files are referenced from [`../defense-deck.html`](../defense-deck.html).  
Recapture requirements: [`../../tasks/DEFENSE_REVIEW_CURSOR_VIDEO.md`](../../tasks/DEFENSE_REVIEW_CURSOR_VIDEO.md) (PRE-02, PRE-08, PRE-19 and others).

Status: **do not mark DONE** until the file is replaced and the caption in the deck is updated.

## Already available (keep or refine the caption)

| File | Contents | Note |
|------|------------|-----------|
| `ui-chat.png` | Chat · allergen gluten/nuts + citations · OLLAMA allow | Updated · slide 6 |
| `ui-labels.png` | Labels | Appendix · OCR mock / future |
| `ui-llm.png` | LLM Settings | Appendix |
| `ui-graph.png` | Graph seed=gluten · source=neo4j | OK for slide 7 |
| `ui-ops.png` | Ops · live · OLLAMA · audit `trace_id` ≠ null | **Available** · slide 11 |
| `ui-acl-manager-deny.png` | manager deny | **PRE-08:** the question contains 42%; recapture |
| `ui-acl-compliance-allow.png` | compliance allow | **PRE-08:** recapture the same question without the number; verify the summary |
| `grafana-kp-overview-1.png` | KP Overview traffic | Captions: p50/p95, UP=scrape |
| `grafana-kp-overview-2.png` | tokens / totals | Captions: input/output, application status |
| `grafana-acl-denies.png` | deny rate | Historical example; "deny decisions / min" |
| `grafana-tempo.png` | Tempo Explore · **POST /v1/chat** · spans graph/vector/rerank/llm/output_guard | **Available** · slide 10 | **PRE-02:** currently GET `/v1/llm/config`, which is **invalid for chat** |

## New capture required (before recording)

| File | How | Acceptance |
|------|-----|---------|
| `grafana-tempo.png` | Explore → Tempo → POST /v1/chat with spans expanded | **Available** · slide 10 |
| `ui-acl-manager-deny.png` | Clean session, manager role, question: `What is the target margin in the Q4 Closed Promo Margin Playbook?` (without "42%"). | No secret source and no facts from it. |
| `ui-acl-compliance-allow.png` | Clean session, same question, compliance role. | Source is accessible; separately verify that the answer summarizes the margin correctly. |
| `ui-ops.png` | Ops after a chat with `trace_id` | **Available** · slide 11 |
| `neo4j-browser.png` | http://127.0.0.1:30474 + gluten Cypher path | **Available** · slide 7 · HAS_ALLERGEN / GOVERNS |

### Optional

| File | How |
|------|-----|
| `ui-chat-allergen-answer.png` | Chat → allergen prompt → answer + citations · `degraded=false` |
| `grafana-loki.png` | Explore → Loki · with a non-null trace_id |
| Grafana single-panel crops | UP, req/min, RAG p95, deny/min, large and without the side menu |

After replacing a PNG, update `src` / remove the "New capture required" blocks on slides 7, 9, 10, 11.
