import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from app.api.restful import (
    api_routes,
    app_route_violations,
    route_violation,
    route_violations,
    stale_custom_routes,
)
from app.main import app, create_app

COPY = ("POST", "/api/routines/{id}/copy")
ORDER = ("PUT", "/api/routines/{routine_id}/workouts/order")
UPSERT = ("PUT", "/api/set-records/{id}")


def test_every_api_route_follows_the_rules() -> None:
    assert app_route_violations(app) == []


def test_the_rules_see_routes_in_included_routers() -> None:
    # FastAPI keeps included routers as wrappers in app.routes, so a check that only looked at
    # app.routes itself would pass without seeing any /api route
    assert ("GET", "/api/health", "show") in set(api_routes(app.routes))
    test_app = create_app()
    things = APIRouter(prefix="/things", tags=["things"])

    @things.get("/{id}")
    def get_thing() -> None: ...

    api = APIRouter(prefix="/api")
    api.include_router(things)
    test_app.include_router(api)

    assert any("GET /api/things/{id} (get_thing)" in p for p in app_route_violations(test_app))


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
        ("GET", "/api/workout-exercises/{workout_exercise_id}/sets/new", "new"),
        ("POST", "/api/workout-exercises/{workout_exercise_id}/sets", "create"),
        ("GET", "/api/exercises/{exercise_id}/set-records", "index"),
        # Singular resources
        ("GET", "/api/profile", "show"),
        ("PATCH", "/api/profile", "update"),
        ("POST", "/api/registration", "create"),
        ("POST", "/api/session", "create"),
        ("DELETE", "/api/session", "destroy"),
        ("GET", "/api/health", "show"),
    ],
)
def test_standard_actions_are_allowed(method: str, path: str, name: str) -> None:
    assert route_violation(method, path, name, custom_routes={}) is None


@pytest.mark.parametrize(
    ("method", "path", "name", "reason"),
    [
        ("PUT", "/api/exercises/{id}", "update", "must use PATCH"),
        ("GET", "/api/exercises/{id}", "get_exercise", "name the function after an action"),
        ("GET", "/api/routines/{routine_id}/workouts/{id}", "show", "doesn't fit"),
        ("GET", "/api/routines/{id}/workouts", "index", "doesn't fit"),
        ("GET", "/api/exercises/{exercise_id}", "show", "doesn't fit"),
        ("GET", "/api/Exercises", "index", "doesn't fit"),
        ("GET", "/api/workout_exercises", "index", "doesn't fit"),
        ("POST", "/api/exercises/{id}", "create", "doesn't fit"),
        ("GET", "/exercises", "index", "under /api/"),
        # The parent parameter must name its parent
        ("GET", "/api/routines/{exercise_id}/workouts", "index", "should be {routine_id}"),
        (
            "POST",
            "/api/workout-exercises/{workout_id}/sets",
            "create",
            "should be {workout_exercise_id}",
        ),
        # Plural resources need {id} for member actions; singular ones have no index or {id}
        ("GET", "/api/exercises", "show", "needs /{id}"),
        ("PATCH", "/api/exercises", "update", "needs /{id}"),
        ("GET", "/api/profile", "index", "`profile` is singular"),
        ("GET", "/api/health/{id}", "show", "`health` is singular"),
        ("GET", "/api/session/{session_id}/devices", "index", "`session` is singular"),
    ],
)
def test_malformed_standard_routes_are_rejected(
    method: str, path: str, name: str, reason: str
) -> None:
    violation = route_violation(method, path, name, custom_routes={})

    assert violation is not None
    assert reason in violation


@pytest.mark.parametrize(("route", "name"), [(COPY, "copy"), (ORDER, "order"), (UPSERT, "upsert")])
def test_unregistered_custom_routes_are_rejected(route: tuple[str, str], name: str) -> None:
    violation = route_violation(*route, name, custom_routes={})

    assert violation is not None
    assert "register it in CUSTOM_ROUTES" in violation


@pytest.mark.parametrize(("route", "name"), [(COPY, "copy"), (ORDER, "order"), (UPSERT, "upsert")])
def test_registered_custom_routes_are_allowed(route: tuple[str, str], name: str) -> None:
    registry = {route: "A standard action would hide what this does"}

    assert route_violation(*route, name, custom_routes=registry) is None


def test_a_custom_route_needs_a_reason() -> None:
    violation = route_violation(*COPY, "copy", custom_routes={COPY: "  "})

    assert violation is not None
    assert "reason" in violation


def test_a_custom_route_cant_reuse_a_standard_action_name() -> None:
    violation = route_violation(*UPSERT, "update", custom_routes={UPSERT: "Create or replace"})

    assert violation is not None
    assert "not `update`" in violation


def test_violations_and_stale_entries_are_found_in_a_router() -> None:
    router = APIRouter(prefix="/api/routines", tags=["routines"])

    @router.post("/{id}/copy")
    def copy() -> None: ...

    @router.put("/{id}")
    def update() -> None: ...

    @router.get("/{id}")
    def get_routine() -> None: ...

    @router.get("")
    def index() -> None: ...

    registry = {COPY: "Copying isn't creating from scratch", ORDER: "Bulk reorder"}
    problems = route_violations(router.routes, registry)

    assert len(problems) == 2
    assert any("PUT /api/routines/{id}" in problem for problem in problems)
    assert any("get_routine" in problem for problem in problems)
    assert stale_custom_routes(router.routes, registry) == [ORDER]


def test_operation_ids_are_unique() -> None:
    # FastAPI only warns about duplicates; generated clients would get clashing names. A
    # resource with two nested indexes needs a second tag (see session_set_records.py)
    ids = [op["operationId"] for path in app.openapi()["paths"].values() for op in path.values()]

    assert len(ids) == len(set(ids)), sorted(id for id in ids if ids.count(id) > 1)


def test_operation_ids_read_tag_and_action() -> None:
    operations = app.openapi()["paths"]["/api/health"]

    assert operations["get"]["operationId"] == "health-show"


def test_validation_errors_are_documented_with_the_api_error_shape() -> None:
    test_app = create_app()
    router = APIRouter(prefix="/api/things", tags=["things"])

    class ThingIn(BaseModel):
        name: str

    @router.post("")
    def create(body: ThingIn) -> None: ...

    test_app.include_router(router)
    schema = test_app.openapi()

    response = schema["paths"]["/api/things"]["post"]["responses"]["422"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorBody"
    }
    assert set(schema["components"]["schemas"]["ErrorBody"]["properties"]) == {
        "detail",
        "code",
        "errors",
    }
    assert "HTTPValidationError" not in schema["components"]["schemas"]
