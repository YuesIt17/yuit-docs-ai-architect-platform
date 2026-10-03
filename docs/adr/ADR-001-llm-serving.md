# ADR-001: LLM Serving (air-gapped)

## Status
Accepted

## Context
RetailPartnerX requires on-prem inference without OpenAI/Anthropic SaaS (invert hw-4 SaaS PoC decision for production closed loop).

## Decision
- Serving: **vLLM** (OpenAI-compatible) or **Ollama** for laptop demos; **MOCK** for CI
- Models: Qwen2.5/3-Instruct (RU), DeepSeek-distill alternate
- Quantization: AWQ/GGUF on consumer GPU; KV-cache enabled in vLLM
- Client: single adapter (`LLMClient`) via `OPENAI_BASE_URL`

## Consequences
+ Data residency, controllable latency/cost  
− Ops burden for GPU capacity (see hw-7 sizing)