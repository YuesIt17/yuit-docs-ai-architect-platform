# Model Card — RetailPartnerX Knowledge Platform

## Intended use
Grounded answers for store associates, category managers, compliance officers over Product/Policy/Regulatory KB and packaging labels.

## Out of scope
Medical advice, legal counsel, training foundation models.

## Models
| Component | Default MVP |
|-----------|-------------|
| Chat LLM | MOCK or Qwen2.5-Instruct via vLLM/Ollama |
| Embeddings | Deterministic mock / multilingual-e5-base |
| Vision | Mock OCR extract; optional Qwen-VL |

## Safety
RBAC on retrieval; input injection guard; output ACL; PII redaction in prompts/traces.

## Evaluation
Gold set in `/evals`; Faithfulness-style checks planned (hw-6 thresholds).

## Cost
Audit `cost_est` per request; prefer cache + mock in CI.