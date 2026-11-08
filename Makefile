UV := uv --directory backend

.PHONY: help db-up db-down install dev migrate lint format test

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

db-up: ## Start Postgres in Docker and wait until it's healthy
	docker compose up -d --wait db

db-down: ## Stop Postgres (data is kept in the volume)
	docker compose down

install: ## Install backend dependencies
	$(UV) sync

dev: ## Run the API with auto-reload on http://localhost:8000
	$(UV) run uvicorn app.main:app --reload

migrate: ## Apply database migrations
	$(UV) run alembic upgrade head

lint: ## Check linting and formatting
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Fix lint issues and format code
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test: ## Run the backend tests
	$(UV) run pytest
