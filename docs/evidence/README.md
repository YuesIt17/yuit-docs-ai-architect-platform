# Папка evidence

Сюда кладём воспроизводимые результаты проверок (не придумывать цифры и скриншоты).

## Состав после реального прогона

| Путь | Содержание |
|------|------------|
| `manifest.json` | commit SHA, дата, OS, провайдеры, размер корпуса |
| `pytest.txt` | вывод `pytest -q` |
| `demo_check.json` | вывод `scripts/demo_check.py` |
| `load/` | сырые JSON из `load_smoke.py` (MOCK + Ollama) |
| `trace.md` | Grafana Tempo: trace id + список span для одного chat-запроса |
| `loki.md` | подтверждение, что логи API видны в Loki |
| `manifest.template.json` | пустой шаблон с подсказками по полям |

## Как обновить

```powershell
# Из корня репозитория после hybrid-up (API на :8080 или :30080)
cd app/backend
.\.venv\Scripts\python -m pytest -q | Tee-Object -FilePath ..\..\docs\evidence\pytest.txt

python ..\scripts\demo_check.py --base-url http://127.0.0.1:30080 `
  | Out-File -Encoding utf8 ..\..\docs\evidence\demo_check.json

python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 20 --label mock
# С OLLAMA в Helm/API:
python scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 10 --concurrency 1 --label ollama
```

Заполнить `trace.md` / `loki.md` из Grafana Explore (deep links на Ops-странице). Скопировать `manifest.template.json` → `manifest.json` и указать железо (примеры в комментариях шаблона / capacity-planning).

## Чеклист записи видео

1. Следовать [tasks/AI_PLATFORM_VIDEO_SCRIPT.md](../../tasks/AI_PLATFORM_VIDEO_SCRIPT.md) (5–7 мин).
2. Бинарник видео **не** коммитить.
3. После загрузки проставить `video_url` в `manifest.json`.
4. Экраны: Chat ACL, Graph SVG + Neo4j Browser, Tempo spans, Loki logs, Grafana KP Overview.

Запись видео: [YouTube](https://www.youtube.com/watch?v=y2_mY9_ceuU) · `video_url` в `manifest.json`.
