# Сырые результаты load smoke

| Файл | Провайдер | Заметки |
| ---- | -------- | ------- |
| `smoke_mock_20x1.json` | MOCK | Local uvicorn `:8080` |
| `smoke_ollama_10x1.json` | OLLAMA | `load_smoke` 10×1 hybrid (success 50%, ~16 мин) |
| `smoke_ollama_7x1.json` | OLLAMA | Доп. сэмплы latency `/v1/audit` |
| `last_run.md` | — | Фрагмент из `load_smoke.py --write-report-fragment` |

```powershell
python app/backend/scripts/load_smoke.py --base-url http://127.0.0.1:30080 --count 3 --label ollama --timeout 90 --write-report-fragment
```

Если Ollama «убегает» на длинной генерации: `docker restart retailpartnerx-kp-ollama-1`, затем пересэмплировать из audit или меньшим числом запросов.
