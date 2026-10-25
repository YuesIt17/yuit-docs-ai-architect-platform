# ADR-001: LLM Serving (air-gapped)

## Статус

Accepted

## Контекст

RetailPartnerX требует on-prem инференс без SaaS OpenAI/Anthropic (инверсия решения hw-4 «SaaS для PoC»). Закрытый контур: данные политик, promo и этикеток не покидают периметр. Нужна совместимость с русским языком и возможность демо на consumer GPU.

## Критерии выбора

- OpenAI-compatible API (единый клиент)
- Throughput / KV-cache для batch и chat
- Квантование AWQ/GGUF под ограниченную VRAM
- Простота laptop-демо и CI без GPU

## Варианты

| Вариант | Плюсы | Минусы |
| ------- | ----- | ------ |
| **vLLM** | Высокий throughput, PagedAttention, OpenAI API | Нужен GPU / ops |
| SGLang | Сильный structured/agent serving | Меньше экосистема в курсе |
| TGI | Зрелый HF-стек | Тяжелее ops для MVP |
| **Ollama** | Быстрый laptop-демо | Не prod throughput |
| MOCK | CI / pytest без железа | Не качество ответов |

## Решение

- **Desktop:** Ollama + `qwen2.5:0.5b` (`compose` profile `llm`)
- **CI / unit tests:** MOCK
- **Submission profile:** vLLM OpenAI-compatible
  - Image: `vllm/vllm-openai:v0.6.6`
  - Model: `Qwen/Qwen2.5-1.5B-Instruct-AWQ` (AWQ, context 4096, max-num-seqs 2)
  - Compose profile `vllm`, Helm overlay `values-submission-vllm.yaml`
  - Docs: [docs/infra/vllm-profile.md](../../docs/infra/vllm-profile.md)
- Клиент: единый `LLMClient` (`MOCK` \| `OLLAMA` \| `VLLM`) с allowlist `base_url`
- Если GPU недоступен: конфигурация проверяется статически; статус **«runtime не проверен»**

## Последствия

- (+) Data residency, laptop demo, submission path aligned with course serving engines
- (−) vLLM GPU runtime may remain unverified on CPU-only machines; Ollama is not claimed as vLLM

## Ссылки

- Код: `app/backend/kp/infrastructure/llm.py`
- Continuity: hw-4 (SaaS), hw-7 (sizing)
