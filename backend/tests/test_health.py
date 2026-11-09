from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import get_plain_session
from app.main import app


def test_health_reports_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unavailable_when_database_is_unreachable() -> None:
    # Nothing listens on port 1, so connecting fails immediately
    unreachable = create_engine(
        "postgresql+psycopg://postgres:postgres@127.0.0.1:1/missing",
        connect_args={"connect_timeout": 1},
    )

    def unreachable_db() -> Iterator[Session]:
        with Session(unreachable) as session:
            yield session

    app.dependency_overrides[get_plain_session] = unreachable_db
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/api/health")
    finally:
        app.dependency_overrides.clear()
        unreachable.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_openapi_schema_is_served_under_api(client: TestClient) -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    operation = response.json()["paths"]["/api/health"]["get"]
    assert operation["operationId"] == "health-show"


def test_interactive_docs_are_served_under_api(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200
    assert client.get("/docs").status_code == 404
