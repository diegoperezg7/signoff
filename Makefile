PYTHON ?= /usr/bin/python3

.PHONY: api web dev up down test lint migrate

api:
	cd apps/api && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm install && npm run dev

dev:
	@echo "Start API and web in two terminals: make api / make web"

up:
	docker compose up --build

down:
	docker compose down

test:
	cd apps/api && $(PYTHON) -m pytest -q

migrate:
	cd apps/api && $(PYTHON) -m alembic upgrade head

lint:
	$(PYTHON) -m compileall apps/api/app
	cd apps/web && npm run lint
