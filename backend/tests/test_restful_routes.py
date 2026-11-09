import pytest
from fastapi import APIRouter

from app.api.restful import app_route_violations, route_violation, route_violations
from app.main import app


def test_every_api_route_follows_the_restful_rules() -> None:
    assert app_route_violations(app) == []


@pytest.mark.parametrize(
    ("method", "path", "name"),
    [
        ("GET", "/api/exercises", "index"),
        ("GET", "/api/exercises/new", "new"),
        ("POST", "/api/exercises", "create"),
        ("GET", "/api/exercises/{id}", "show"),
        ("GET", "/api/exercises/{id}/edit", "edit"),
        ("PATCH", "/api/exercises/{id}", "update"),
        ("DELETE", "/api/exercises/{id}", "destroy"),
        # Shallow nesting: collection actions under one parent
        ("GET", "/api/routines/{routine_id}/workouts", "index"),
        ("GET", "/api/routines/{routine_id}/workouts/new", "new"),
        ("POST", "/api/workout-exercises/{workout_exercise_id}/sets", "create"),
        # Singular resources
        ("GET", "/api/profile", "show"),
        ("GET", "/api/profile/edit", "edit"),
        ("PATCH", "/api/profile", "update"),
        ("DELETE", "/api/session", "destroy"),
        ("GET", "/api/health", "show"),
    ],
)
def test_the_seven_actions_are_allowed(method: str, path: str, name: str) -> None:
    assert route_violation(method, path, name) is None


@pytest.mark.parametrize(
    ("method", "path", "name", "reason"),
    [
        ("PUT", "/api/exercises/{id}", "update", "must use PATCH"),
        ("POST", "/api/routines/{id}/copy", "create", "doesn't fit"),
        ("PUT", "/api/routines/{routine_id}/workouts/order", "update", "must use PATCH"),
        ("GET", "/api/exercises/{id}", "get_exercise", "named after an action"),
        ("GET", "/api/routines/{routine_id}/workouts/{id}", "show", "doesn't fit"),
        ("GET", "/api/routines/{id}/workouts", "index", "doesn't fit"),
        ("GET", "/api/exercises/{exercise_id}", "show", "doesn't fit"),
        ("GET", "/api/Exercises", "index", "doesn't fit"),
        ("GET", "/api/workout_exercises", "index", "doesn't fit"),
        ("POST", "/api/exercises/{id}", "create", "doesn't fit"),
        ("GET", "/exercises", "index", "under /api/"),
    ],
)
def test_other_routes_are_rejected(method: str, path: str, name: str, reason: str) -> None:
    violation = route_violation(method, path, name)

    assert violation is not None
    assert reason in violation


def test_violations_are_found_in_a_router() -> None:
    router = APIRouter(prefix="/api/routines", tags=["routines"])

    @router.put("/{id}")
    def update() -> None: ...

    @router.post("/{id}/copy")
    def copy() -> None: ...

    @router.get("/{id}")
    def get_routine() -> None: ...

    @router.get("")
    def index() -> None: ...

    problems = route_violations(router.routes)

    assert len(problems) == 3
    assert any("PUT /api/routines/{id}" in problem for problem in problems)
    assert any("/copy" in problem for problem in problems)
    assert any("get_routine" in problem for problem in problems)


def test_operation_ids_read_tag_and_action() -> None:
    operations = app.openapi()["paths"]["/api/health"]

    assert operations["get"]["operationId"] == "health-show"
