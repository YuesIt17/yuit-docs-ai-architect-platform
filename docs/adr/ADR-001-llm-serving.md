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

- Serving: **vLLM** (целевой) или **Ollama** (ноутбук); **MOCK** для CI
- Модели: Qwen2.5/3-Instruct (RU), альтернатива DeepSeek-distill
- Квантование: AWQ/GGUF; KV-cache в vLLM
- Клиент: единый адаптер `LLMClient` через `OPENAI_BASE_URL`

## Последствия

- (+) Data residency, контролируемые latency/cost, единый контракт клиента
- (−) Ops-нагрузка по GPU (см. hw-7 sizing); на demo-ноутбуке — маленькая модель / offloading

## Ссылки

- Код: `backend/app/services/llm.py`
- Continuity: hw-4 (SaaS), hw-7 (sizing)
