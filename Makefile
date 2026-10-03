.PHONY: up down demo seed test lint api docs

up:
	docker compose -f infra/docker-compose.yml --profile core up -d

down:
	docker compose -f infra/docker-compose.yml --profile core --profile demo --profile llm --profile vision down -v

demo:
	docker compose -f infra/docker-compose.yml --profile demo up -d --build

seed:
	cd backend && python -m pipelines.seed_all

api:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test:
	cd backend && pytest -q

evals:
	cd backend && pytest ../evals -q

load-smoke:
	cd backend && python -m scripts.load_smoke