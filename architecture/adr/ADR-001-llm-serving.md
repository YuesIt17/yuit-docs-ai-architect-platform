# ADR-001: LLM Serving (air-gapped)

## Status

Accepted

## Context

RetailPartnerX requires on-prem inference without SaaS OpenAI/Anthropic (this reverses the hw-4 decision to use SaaS for the PoC). In the closed perimeter, policy, promo and label data never leave the boundary. The platform needs multilingual model support and must be able to run a demo on a consumer GPU.

## Selection criteria

- OpenAI-compatible API (a single client)
- Throughput / KV cache for batch and chat
- AWQ/GGUF quantization for limited VRAM
- Simple laptop demo and CI without a GPU

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **vLLM** | High throughput, PagedAttention, OpenAI API | Requires a GPU and ops |
| SGLang | Strong structured/agent serving | Smaller ecosystem within the course |
| TGI | Mature HF stack | Heavier ops for an MVP |
| **Ollama** | Fast laptop demo | Not production throughput |
| MOCK | CI / pytest without hardware | No answer quality |

## Decision

- **Desktop:** Ollama + `qwen2.5:0.5b` (`compose` profile `llm`)
- **CI / unit tests:** MOCK
- **Submission profile:** vLLM OpenAI-compatible
  - Image: `vllm/vllm-openai:v0.6.6`
  - Model: `Qwen/Qwen2.5-1.5B-Instruct-AWQ` (AWQ, context 4096, max-num-seqs 2)
  - Compose profile `vllm`, Helm overlay `values-submission-vllm.yaml`
  - Docs: [docs/infra/vllm-profile.md](../../docs/infra/vllm-profile.md)
- Client: a single `LLMClient` (`MOCK` \| `OLLAMA` \| `VLLM`) with a `base_url` allowlist
- If no GPU is available, the configuration is checked statically and its status is **"runtime not verified"**

## Consequences

- (+) Data residency, laptop demo, submission path aligned with course serving engines
- (−) vLLM GPU runtime may remain unverified on CPU-only machines; Ollama is not claimed as vLLM

## References

- Code: `app/backend/kp/infrastructure/llm.py`
- Continuity: hw-4 (SaaS), hw-7 (sizing)
