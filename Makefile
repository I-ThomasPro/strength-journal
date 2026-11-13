UV := uv --directory backend
# Run pnpm inside frontend/, not with --dir: Corepack picks the pnpm version from the
# package.json where it starts, and only frontend/ has one (its packageManager field)
PNPM := cd frontend && pnpm

.PHONY: help db-up db-down install dev migrate create-admin lint format test openapi
.PHONY: fe-install fe-dev fe-build fe-lint fe-format fe-test

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

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

create-admin: ## Create an admin account (asks for its username, name and password)
	$(UV) run python -m app.cli create-admin

lint: ## Check linting and formatting
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Fix lint issues and format code
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

test: ## Run the backend tests
	$(UV) run pytest

openapi: ## Export the API schema to frontend/openapi.json (after any API change)
	$(UV) run python -m app.openapi ../frontend/openapi.json

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
