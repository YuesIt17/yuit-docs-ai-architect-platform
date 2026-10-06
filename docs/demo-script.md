# Скрипт демо (5–7 мин)

Цель: показать «под капотом» GraphRAG, ACL, observability и multimodal path.

| Мин | Шаг | Действие | Ожидаемый результат |
| --- | --- | -------- | ------------------- |
| 0:00 | Bring-up | `make demo` (или API+UI). Открыть http://localhost:5173 | UI живой, health OK |
| 0:40 | LLM | Страница `/llm`: MOCK → Probe → Apply | Chat badge `model_uri=mock://…` |
| 1:20 | ACL deny | Роль `manager`, вопрос про секретный promo / margin | Нет утечки `42%` / secret citations |
| 2:20 | ACL allow | Роль `compliance`, тот же вопрос | Citations по secret документу |
| 3:20 | Labels | `/labels`: upload fixture как `label.png` | Extract JSON + S3 URI + policy notes |
| 4:20 | Graph | Neo4j Browser :7474 (compose) / страница Graph | Узлы Document/Chunk/Entity |
| 5:00 | Ops / traces | Jaeger :16686, Prometheus :9090, `/ops` audit | Span chat; метрики; audit row |
| 5:40 | (опц.) Ollama | `make llm-ollama`, Apply OLLAMA | Ответ с `llm_provider=OLLAMA` |
| 6:20 | (опц.) K8s | `.\scripts\k8s-up.ps1` → http://kp.local:8088 | Тот же UX в кластере |

**Запись видео:** пройти таблицу сверху вниз, держать фокус на ACL и трейсах.

См. [SETUP.md](SETUP.md), [SRE.md](SRE.md).
