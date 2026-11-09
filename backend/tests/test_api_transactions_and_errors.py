"""Request transactions and the error format, through a test-only app"""

import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi import APIRouter, FastAPI, status
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.db import DbSession
from app.main import create_app
from app.models.exercise import Exercise
from app.models.set import Set
from tests.factories import create_exercise, create_set, create_workout_exercise
from tests.helpers import assert_error


class ExerciseIn(BaseModel):
    name: str


class Weight(BaseModel):
    weight: Decimal


def build_app() -> FastAPI:
    app = create_app()
    router = APIRouter(prefix="/api/test", tags=["test"])

    @router.post("/exercises", status_code=status.HTTP_201_CREATED)
    def create(body: ExerciseIn, db: DbSession) -> dict[str, str]:
        exercise = Exercise(name=body.name)
        db.add(exercise)
        db.flush()
        return {"id": str(exercise.id)}

    @router.post("/exercises/then-fail")
    def create_then_fail(body: ExerciseIn, db: DbSession) -> None:
        db.add(Exercise(name=body.name))
        db.flush()
        raise not_found("Pretend the parent was missing")

    @router.delete("/exercises/{id}", status_code=status.HTTP_204_NO_CONTENT)
    def destroy(id: uuid.UUID, db: DbSession) -> None:
        db.delete(db.get(Exercise, id))

    @router.post("/sets/{id}/negative-reps")
    def break_check(id: uuid.UUID, db: DbSession) -> None:
        db.get(Set, id).target_reps = -1

    @router.get("/weight")
    def show() -> Weight:
        return Weight(weight=Decimal("102.50"))

    app.include_router(router)
    return app


@pytest.fixture
def test_client(client_for: Callable[[FastAPI], TestClient]) -> TestClient:
    return client_for(build_app())


def exercise_named(db_session: Session, name: str) -> Exercise | None:
    db_session.expire_all()
    return db_session.query(Exercise).filter_by(name=name).one_or_none()


def test_a_successful_request_commits(test_client: TestClient, db_session: Session) -> None:
    response = test_client.post("/api/test/exercises", json={"name": "Committed"})

    assert response.status_code == 201
    assert exercise_named(db_session, "Committed") is not None


def test_an_error_rolls_the_request_back(test_client: TestClient, db_session: Session) -> None:
    response = test_client.post("/api/test/exercises/then-fail", json={"name": "Rolled Back"})

    assert_error(response, 404, "not_found")
    assert exercise_named(db_session, "Rolled Back") is None


def test_a_unique_violation_at_flush_is_a_409(test_client: TestClient) -> None:
    test_client.post("/api/test/exercises", json={"name": "Squat"})
    response = test_client.post("/api/test/exercises", json={"name": "squat"})

    assert_error(response, 409, "duplicate_name")


def test_a_deferred_violation_at_commit_is_a_409_and_rolls_back(
    test_client: TestClient, db_session: Session
) -> None:
    exercise = create_exercise(db_session, name="In Use")
    create_workout_exercise(db_session, exercise=exercise)

    response = test_client.delete(f"/api/test/exercises/{exercise.id}")

    assert_error(response, 409, "exercise_in_use")
    assert exercise_named(db_session, "In Use") is not None


def test_a_check_violation_is_a_422(test_client: TestClient, db_session: Session) -> None:
    set_ = create_set(db_session)

    response = test_client.post(f"/api/test/sets/{set_.id}/negative-reps")

    assert_error(response, 422, "invalid")


def test_request_validation_errors_list_the_fields(test_client: TestClient) -> None:
    response = test_client.post("/api/test/exercises", json={})

    body = assert_error(response, 422, "invalid")
    assert body["errors"][0]["loc"] == ["body", "name"]


def test_unknown_routes_and_methods_use_the_error_format(test_client: TestClient) -> None:
    assert_error(test_client.get("/api/test/missing"), 404, "not_found")
    assert_error(test_client.put("/api/test/exercises"), 405, "method_not_allowed")


def test_decimals_are_serialized_as_exact_strings(test_client: TestClient) -> None:
    assert test_client.get("/api/test/weight").json() == {"weight": "102.50"}
