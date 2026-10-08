.PHONY: help up down logs test test-api test-web lint fmt seed

help:
	@echo "Emberline"
	@echo "  make up        docker compose up --build"
	@echo "  make down      docker compose down"
	@echo "  make logs      follow api+web logs"
	@echo "  make test      backend pytest + frontend vitest"
	@echo "  make test-api  pytest in backend/"
	@echo "  make test-web  vitest in frontend/"

up:
	cd frontend && npm install && npm run build
	docker compose up --build -d

up-debug:
	cd frontend && npm install && npm run build
	docker compose -f docker-compose.yml -f docker-compose.debug.yml up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api web

test: test-api test-web

test-api:
	cd ../kernel && python -m pip install -e ".[dev]" -q
	cd backend && PYTHONPATH=../../kernel python -m pytest

test-web:
	cd frontend && npm test

seed:
	@echo "Demo user is seeded on API boot: owner@emberlinedesk.com / emberline-demo"
