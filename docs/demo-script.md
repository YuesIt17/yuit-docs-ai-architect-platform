# Скрипт демо (5–7 мин)

Цель: показать «под капотом» GraphRAG, ACL, observability и multimodal path.

| Мин | Шаг | Действие | Ожидаемый результат |
| --- | --- | -------- | ------------------- |
| 0:00 | Bring-up | `.\scripts\hybrid-up.ps1` → http://kp.local:8088 | UI живой, health OK |
| 0:40 | LLM | Страница `/llm`: MOCK → Probe → Apply (или уже OLLAMA) | badge `model_uri=…` |
| 1:20 | ACL deny | Роль `manager`, вопрос про секретный promo / margin | Нет утечки `42%` / secret citations |
| 2:20 | ACL allow | Роль `compliance`, тот же вопрос | Citations по secret документу |
| 3:20 | Labels | `/labels`: upload fixture как `label.png` | Extract JSON + S3 URI + policy notes |
| 4:20 | Graph | Graph page / Neo4j port-forward | Узлы Document/Chunk/Entity |
| 5:00 | Ops / traces | Jaeger :16686, Prometheus :9090, `/ops` audit | Span chat; метрики; audit row |
| 5:40 | (опц.) Ollama | Apply OLLAMA `host.docker.internal:11434/v1` | `llm_provider=OLLAMA` |

**Запись видео:** пройти таблицу сверху вниз, держать фокус на ACL и трейсах.

См. [SETUP.md](SETUP.md), [SRE.md](SRE.md).
