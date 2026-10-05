# Demo Script (5–7 min)

1. **Bring-up** — `make demo` (or `npm run dev` + API). Open UI http://localhost:5173.
2. **LLM** — `/llm` page: show MOCK, Probe, Apply. Chat answer badge shows `model_uri`.
3. **ACL** — Role `manager`, secret promo prompt → no `42%`. Switch `compliance` → secret citations.
4. **Labels** — Upload fixture as `label.png`; show extract + S3 URIs.
5. **Graph / Ops** — stats, outbox, audit, deep links.
6. **Optional Ollama** — `make llm-ollama`, Apply OLLAMA in UI, re-chat.
7. **Optional K8s** — `.\scripts\k8s-up.ps1`, open `http://kp.local:8088`.