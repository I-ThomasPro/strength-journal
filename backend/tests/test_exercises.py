"""Library and custom exercises"""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.user import User
from tests.factories import (
    create_exercise,
    create_routine,
    create_set_record,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


@pytest.fixture
def tag() -> str:
    """A word to put in test exercises' names, so searches only find this test's exercises"""
    return uuid.uuid4().hex[:8]


def names(response_json: dict) -> list[str]:
    return [item["name"] for item in response_json["items"]]


def exists(db_session: Session, exercise: Exercise) -> bool:
    db_session.expire_all()
    return db_session.get(Exercise, exercise.id) is not None


# Index


@pytest.fixture
def mixed_exercises(db_session: Session, current_user: User, tag: str) -> None:
    """Two library exercises, two of the current user's, and one of another user's"""
    create_exercise(db_session, name=f"Back Squat {tag}")
    create_exercise(db_session, name=f"bench press {tag}")
    create_exercise(db_session, name=f"Zercher Squat {tag}", owner=current_user)
    create_exercise(db_session, name=f"Bench Press {tag}", owner=current_user)
    create_exercise(db_session, name=f"Arnold Press {tag}", owner=create_user(db_session))


@pytest.mark.usefixtures("mixed_exercises")
@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        # Ordered by name ignoring case; library first when the names match
        ("all", ["Back Squat", "bench press", "Bench Press", "Zercher Squat"]),
        ("library", ["Back Squat", "bench press"]),
        ("mine", ["Bench Press", "Zercher Squat"]),
    ],
)
def test_each_scope_lists_its_exercises_by_name(
    logged_in_client: TestClient, tag: str, scope: str, expected: list[str]
) -> None:
    response = logged_in_client.get("/api/exercises", params={"scope": scope, "q": tag})

    assert response.status_code == 200, response.text
    body = response.json()
    assert names(body) == [f"{name} {tag}" for name in expected]
    assert body["total"] == len(expected)


@pytest.mark.usefixtures("mixed_exercises")
def test_the_default_scope_is_all(logged_in_client: TestClient, tag: str) -> None:
    body = logged_in_client.get("/api/exercises", params={"q": tag}).json()

    assert body["total"] == 4
    assert [item["is_library"] for item in body["items"]] == [True, True, False, False]


@pytest.mark.usefixtures("mixed_exercises")
def test_the_search_matches_part_of_the_name_ignoring_case(
    logged_in_client: TestClient, tag: str
) -> None:
    body = logged_in_client.get("/api/exercises", params={"q": f"SQUAT {tag}"}).json()

    assert names(body) == [f"Back Squat {tag}", f"Zercher Squat {tag}"]


def test_search_wildcards_match_literally(
    logged_in_client: TestClient, db_session: Session, tag: str
) -> None:
    create_exercise(db_session, name=f"100% Effort {tag}")
    create_exercise(db_session, name=f"Easy Effort {tag}")

    assert names(
        logged_in_client.get("/api/exercises", params={"q": f"% Effort {tag}"}).json()
    ) == [f"100% Effort {tag}"]
    assert logged_in_client.get("/api/exercises", params={"q": "_" * 8}).json()["total"] == 0


@pytest.mark.usefixtures("mixed_exercises")
def test_the_index_is_paged(logged_in_client: TestClient, tag: str) -> None:
    params = {"q": tag, "limit": 2, "offset": 1}

    body = logged_in_client.get("/api/exercises", params=params).json()

    assert names(body) == [f"bench press {tag}", f"Bench Press {tag}"]
    assert body["total"] == 4


def test_an_unknown_scope_is_rejected(logged_in_client: TestClient) -> None:
    assert_error(logged_in_client.get("/api/exercises?scope=everyone"), 422, "invalid")


# Create


def test_creating_a_custom_exercise(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    response = logged_in_client.post("/api/exercises", json={"name": "  Pendlay Row  "})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Pendlay Row"
    assert body["type"] == "strength"
    assert body["is_library"] is False
    assert body["created_at"] and body["updated_at"]
    exercise = db_session.get(Exercise, uuid.UUID(body["id"]))
    assert exercise is not None and exercise.owner_id == current_user.id


def test_a_duplicate_name_is_rejected_ignoring_case(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    create_exercise(db_session, name="Pendlay Row", owner=current_user)

    response = logged_in_client.post("/api/exercises", json={"name": "PENDLAY ROW"})

    assert_error(response, 409, "duplicate_name")


def test_a_library_or_another_users_name_can_be_reused(
    logged_in_client: TestClient, db_session: Session
) -> None:
    create_exercise(db_session, name="Pendlay Row")
    create_exercise(db_session, name="Seal Row", owner=create_user(db_session))

    for name in ["Pendlay Row", "Seal Row"]:
        assert logged_in_client.post("/api/exercises", json={"name": name}).status_code == 201


@pytest.mark.parametrize(
    "body",
    [{}, {"name": "   "}, {"name": "x" * 101}, {"name": "Row", "type": "cardio"}],
)
def test_invalid_exercises_are_rejected(logged_in_client: TestClient, body: dict) -> None:
    assert_error(logged_in_client.post("/api/exercises", json=body), 422, "invalid")


# Show


def test_showing_library_and_own_exercises(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    library = create_exercise(db_session)
    own = create_exercise(db_session, owner=current_user)

    for exercise in [library, own]:
        response = logged_in_client.get(f"/api/exercises/{exercise.id}")
        assert response.status_code == 200
        assert response.json()["name"] == exercise.name
        assert response.json()["is_library"] is (exercise is library)


def test_another_users_exercise_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))

    assert_error(logged_in_client.get(f"/api/exercises/{theirs.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/exercises/{uuid.uuid4()}"), 404, "not_found")


# Update


def test_updating_an_own_exercise(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    exercise = create_exercise(db_session, name="Pendlay Row", owner=current_user)
    before = logged_in_client.get(f"/api/exercises/{exercise.id}").json()

    response = logged_in_client.patch(f"/api/exercises/{exercise.id}", json={"name": "Barbell Row"})

    assert response.status_code == 200, response.text
    after = response.json()
    assert after["name"] == "Barbell Row"
    assert after["type"] == before["type"]
    assert after["updated_at"] >= before["updated_at"]


def test_renaming_to_a_duplicate_is_rejected(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    create_exercise(db_session, name="Pendlay Row", owner=current_user)
    exercise = create_exercise(db_session, name="Seal Row", owner=current_user)

    response = logged_in_client.patch(f"/api/exercises/{exercise.id}", json={"name": "pendlay row"})

    assert_error(response, 409, "duplicate_name")


@pytest.mark.parametrize("body", [{"name": None}, {"type": None}, {"name": ""}])
def test_invalid_updates_are_rejected(
    logged_in_client: TestClient, db_session: Session, current_user: User, body: dict
) -> None:
    exercise = create_exercise(db_session, owner=current_user)

    assert_error(logged_in_client.patch(f"/api/exercises/{exercise.id}", json=body), 422, "invalid")


# Library and other users' exercises can't be changed


def test_library_exercises_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library = create_exercise(db_session, name="Deadlift")
    path = f"/api/exercises/{library.id}"

    assert_error(logged_in_client.patch(path, json={"name": "Renamed"}), 403, "read_only")
    assert_error(logged_in_client.delete(path), 403, "read_only")
    assert exists(db_session, library)
    assert db_session.get(Exercise, library.id).name == "Deadlift"


def test_another_users_exercise_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_exercise(db_session, name="Seal Row", owner=create_user(db_session))
    path = f"/api/exercises/{theirs.id}"

    assert_error(logged_in_client.patch(path, json={"name": "Mine now"}), 404, "not_found")
    assert_error(logged_in_client.delete(path), 404, "not_found")
    db_session.refresh(theirs)
    assert theirs.name == "Seal Row"


# Destroy


def test_deleting_an_own_exercise(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    exercise = create_exercise(db_session, owner=current_user)

    assert logged_in_client.delete(f"/api/exercises/{exercise.id}").status_code == 204
    assert not exists(db_session, exercise)


@pytest.mark.parametrize(
    "use",
    [
        lambda db, user, exercise: create_workout_exercise(
            db, create_workout(db, create_routine(db, owner=user)), exercise
        ),
        lambda db, user, exercise: create_set_record(db, user=user, exercise=exercise),
    ],
    ids=["workout", "set_record"],
)
def test_deleting_an_exercise_in_use_is_a_409(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    use: Callable[[Session, User, Exercise], object],
) -> None:
    exercise = create_exercise(db_session, owner=current_user)
    use(db_session, current_user, exercise)

    response = logged_in_client.delete(f"/api/exercises/{exercise.id}")

    assert_error(response, 409, "exercise_in_use")
    assert exists(db_session, exercise)


def test_exercises_need_a_login(client: TestClient) -> None:
    assert_error(client.get("/api/exercises"), 401, "not_authenticated")
