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

- Runtime MVP: **Ollama** (laptop) + **MOCK** (CI / стабильное демо)
- Модель демо: `qwen2.5:0.5b` (лёгкая); крупнее — по желанию в Ollama
- Клиент: единый адаптер `LLMClient` через OpenAI-compatible API
- **vLLM** остаётся в таблице альтернатив (prod GPU throughput), в runtime MVP **не** подключается

## Последствия

- (+) Data residency, простой closed loop на ноутбуке, единый контракт клиента
- (−) Ollama 0.5B слабее по качеству ответа; prod throughput — отдельный этап (hw-7 / vLLM вне MVP)

## Ссылки

- Код: `backend/app/services/llm.py`
- Continuity: hw-4 (SaaS), hw-7 (sizing)
