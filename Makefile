UV := uv --directory backend
PNPM := pnpm --dir frontend

.PHONY: help db-up db-down install dev migrate lint format test
.PHONY: fe-install fe-dev fe-build fe-lint fe-format fe-test

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-11s %s\n", $$1, $$2}'

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

fe-install: ## Install frontend dependencies
	$(PNPM) install

fe-dev: ## Run the frontend on http://localhost:5173, proxying /api to the API
	$(PNPM) dev

fe-build: ## Typecheck and build the frontend into frontend/dist
	$(PNPM) build

fe-lint: ## Lint, check formatting and typecheck the frontend
	$(PNPM) lint
	$(PNPM) format:check
	$(PNPM) typecheck

fe-format: ## Fix frontend lint issues and format code
	$(PNPM) lint --fix
	$(PNPM) format

fe-test: ## Run the frontend tests
	$(PNPM) test
