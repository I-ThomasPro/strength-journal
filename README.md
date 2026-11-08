# strength-journal
A simple web app for tracking and measuring training data with an emphasis on strength training.

## Backend

The API is a [FastAPI](https://fastapi.tiangolo.com/) app in `backend/`, using SQLAlchemy 2 and Alembic on PostgreSQL. All routes live under `/api`.

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you if needed)
- Docker, for the local Postgres database (or your own Postgres with the URLs in `backend/.env`)

### Quick start
```bash
make db-up      # start Postgres 18 (creates strength_journal and strength_journal_test)
make install    # install dependencies into backend/.venv
make migrate    # apply database migrations
make dev        # run the API on http://localhost:8000
```

Then open:
- http://localhost:8000/api/health to check the API can reach the database
- http://localhost:8000/api/docs for interactive API docs

Settings come from environment variables or `backend/.env`. Copy `backend/.env.example` to get started.

### Tests and linting
```bash
make test       # pytest against strength_journal_test
make lint       # ruff lint + format check
make format     # auto-fix lint issues and format
```

Tests migrate the test database to the latest revision, then run each test inside a transaction that's rolled back afterwards.

### Migrations
```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Import new model modules in `backend/alembic/env.py` so autogenerate can see them. CI fails if the models and migrations disagree (`alembic check`).

### Layout
```
backend/
├── app/
│   ├── main.py          # create_app(): routers, docs under /api
│   ├── config.py        # Settings (pydantic-settings)
│   ├── db.py            # Base, engine, get_db / DbSession dependency
│   └── api/
│       ├── router.py    # /api router
│       └── routes/      # one module per resource
├── alembic/             # migration environment and versions/
└── tests/
```
