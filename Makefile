.PHONY: up down migrate test lint frontend-install backend-install bootstrap-hint seed-reddit

up:
	docker compose up --build

down:
	docker compose down

migrate:
	cd backend && DJANGO_ENV=local python manage.py migrate

test:
	cd backend && DJANGO_ENV=test python -m pytest tests/
	cd frontend && npm run build

lint:
	cd backend && ruff check . || true
	cd frontend && npm run lint || true

frontend-install:
	cd frontend && npm install

backend-install:
	cd backend && pip install -r requirements-dev.txt

seed-reddit:
	cd backend && DJANGO_ENV=local REDDIT_MODE=fixture python manage.py seed_dev_reddit --poll

bootstrap-hint:
	@echo "With ALLOW_BOOTSTRAP=true and zero users:"
	@echo "  curl -c cookies.txt http://localhost:8000/api/v1/auth/csrf/"
	@echo "  # then POST /api/v1/auth/bootstrap/ with X-CSRFToken"
