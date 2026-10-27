# Скрины для defense-deck

Файлы подключаются из [`../defense-deck.html`](../defense-deck.html).  
Требования к пересъёмке: [`../../tasks/DEFENSE_REVIEW_CURSOR_VIDEO.md`](../../tasks/DEFENSE_REVIEW_CURSOR_VIDEO.md) (PRE-02, PRE-08, PRE-19 и др.).

Статус: **не ставить DONE**, пока файл не заменён и подпись в deck не обновлена.

## Уже есть (можно оставить / уточнить подпись)

| Файл | Содержание | Замечание |
|------|------------|-----------|
| `ui-chat.png` | Chat · allergen gluten/nuts + citations · OLLAMA allow | Обновлён · слайд 6 |
| `ui-labels.png` | Labels | Appendix · OCR mock / future |
| `ui-llm.png` | LLM Settings | Appendix |
| `ui-graph.png` | Graph seed=gluten · source=neo4j | Ок для слайда 7 |
| `ui-ops.png` | Ops · live · OLLAMA · audit `trace_id` ≠ null | **Есть** · слайд 11 |
| `ui-acl-manager-deny.png` | manager deny | **PRE-08:** вопрос содержит 42% — переснять |
| `ui-acl-compliance-allow.png` | compliance allow | **PRE-08:** переснять тот же вопрос без цифры; проверить пересказ |
| `grafana-kp-overview-1.png` | KP Overview traffic | Подписи: p50/p95, UP=scrape |
| `grafana-kp-overview-2.png` | tokens / totals | Подписи: input/output, прикладные status |
| `grafana-acl-denies.png` | deny rate | Исторический пример; «решения deny / мин» |
| `grafana-tempo.png` | Tempo Explore · **POST /v1/chat** · spans graph/vector/rerank/llm/output_guard | **Есть** · слайд 10 | **PRE-02:** сейчас GET `/v1/llm/config` — **невалидно для chat** |

## Нужен новый захват (обязательно до записи)

| Файл | Как | Приёмка |
|------|-----|---------|
| `grafana-tempo.png` | Explore → Tempo → POST /v1/chat с раскрытыми spans | **Есть** · слайд 10 |
| `ui-acl-manager-deny.png` | Чистый сеанс, роль manager, вопрос: `Какова целевая маржа в Q4 Closed Promo Margin Playbook?` (без «42%»). | Нет секретного источника и фактов из него. |
| `ui-acl-compliance-allow.png` | Чистый сеанс, тот же вопрос, роль compliance. | Источник доступен; отдельно проверить, что ответ верно пересказывает маржу. |
| `ui-ops.png` | Ops после chat с `trace_id` | **Есть** · слайд 11 |
| `neo4j-browser.png` | http://127.0.0.1:30474 + path Cypher gluten | **Есть** · слайд 7 · HAS_ALLERGEN / GOVERNS |

### Опционально

| Файл | Как |
|------|-----|
| `ui-chat-allergen-answer.png` | Chat → allergen prompt → ответ + citations · `degraded=false` |
| `grafana-loki.png` | Explore → Loki · с ненулевым trace_id |
| Grafana single-panel crops | UP, req/min, RAG p95, deny/min — крупно без бокового меню |

После замены PNG обновить `src` / убрать блоки «Нужен новый захват» на слайдах 7, 9, 10, 11.
