# Нагрузочный отчёт

> Учебные smoke-замеры. Это **не** production SLO и не замена GPU/vLLM стенда. См. [capacity-planning.md](capacity-planning.md).

Сырые JSON: [`docs/evidence/load/`](evidence/load/).

## 1. MOCK smoke (baseline API + GraphRAG + ACL)

| Параметр | Значение |
| -------- | -------- |
| Сценарий | GraphRAG chat path, ACL on |
| LLM | MOCK (нулевая генерация) |
| Запросов / concurrency | 20 / 1 |
| Цель | потолок API+RAG без GPU |

| Метрика | Значение | Условия |
| ------- | -------- | ------- |
| RPS (approx) | ~79.5 | local uvicorn MOCK · 2026-10-26 |
| Latency avg | ~12.6 ms | |
| Latency p50 / p95 | ~12.0 / ~15.8 ms | |
| Success rate | 100% | 20 / 1 |
| Raw | [`evidence/load/smoke_mock_20x1.json`](evidence/load/smoke_mock_20x1.json) | |

Повторить: `python app/backend/scripts/load_smoke.py --label mock --count 20` (против live API с `LLM_PROVIDER=MOCK`).

## 2. Ollama E2E (desktop)

| Параметр | Значение |
| -------- | -------- |
| Сценарий | HTTP `/v1/chat` E2E (live store + Ollama) |
| LLM | Ollama `qwen2.5:0.5b` (Q4_K_M) |
| Железо | capacity-planning (i7-8550U, ~32 GB RAM, CPU-only) |
| Захват | 2026-10-26 после `hybrid-up` |
| Источник | `load_smoke.py` → NodePort `:30080` |

```bash
python app/backend/scripts/load_smoke.py \
  --base-url http://127.0.0.1:30080 \
  --count 10 --concurrency 1 --label ollama --timeout 180
```

> Прогон ~16 мин. На CPU часть запросов упирается в timeout / длинную генерацию → success 50%. Latency ниже — только по **успешным** ответам.

| Метрика | Значение | Примечание |
| ------- | -------- | ---------- |
| RPS (approx) | ~0.011 | wall-clock, включая ошибки |
| Latency avg (ok) | ~7.1 s | CPU 0.5B |
| Latency p50 / p95 (ok) | ~1.3 / ~14.1 s | |
| Latency max (ok) | ~20.1 s | |
| Success rate | 50% (5/10) | timeout / длинная генерация |
| Сырой JSON | [`evidence/load/smoke_ollama_10x1.json`](evidence/load/smoke_ollama_10x1.json) | |

Доп. audit-сэмплы: [`smoke_ollama_7x1.json`](evidence/load/smoke_ollama_7x1.json).

Вывод §2: E2E chat на Ollama desktop — **секунды**, не миллисекунды MOCK; узкое место = LLM.

## 3. Сценарии (дизайн)

| Сценарий | Что измеряем | Комментарий |
| -------- | ------------ | ----------- |
| Chat FAQ (MOCK) | RPS / p95 API+RAG | §1 |
| Chat + ACL deny | корректность фильтра | функциональный, не RPS |
| Label mock OCR | p95 vision path | цель дизайна &lt; 1 s |
| Chat + Ollama | tokens/s, p95 E2E | §2 |
| vLLM GPU | RPS / p95 | **runtime не проверен** без NVIDIA |

## Вывод

На MOCK система держит порядка **~80 RPS** при p95 **~16 ms** — узкое место не GraphRAG ACL. На Ollama desktop `load_smoke` 10×1: p50/p95 **~1.3 / ~14 s** (ok), success **50%** из‑за CPU/timeout. Для submission-профиля с GPU — повторить на vLLM AWQ (см. [vllm-profile](infra/vllm-profile.md)); до верификации статус **runtime не проверен**.
