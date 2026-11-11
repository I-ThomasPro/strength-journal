"""Logging lifts with PUT and a client-generated id, and reading an exercise's history"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.sessions import now
from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.set_record import SetRecord
from app.models.user import User
from tests.factories import create_exercise, create_set_record, create_user
from tests.helpers import assert_error

DAY = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)


@pytest.fixture
def squat(db_session: Session) -> Exercise:
    return create_exercise(db_session, name="Squat")


def record_body(exercise: Exercise, **overrides: object) -> dict:
    return {"exercise_id": str(exercise.id), "reps": 5, "weight": "100"} | overrides


def record_count(db_session: Session, **filters: object) -> int:
    db_session.expire_all()
    statement = select(func.count()).select_from(SetRecord).filter_by(**filters)
    return db_session.scalar(statement) or 0


def history_path(exercise: Exercise) -> str:
    return f"/api/exercises/{exercise.id}/set-records"


# Logging with PUT


def test_put_creates_then_replaces_a_record(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    path = f"/api/set-records/{uuid.uuid4()}"
    body = record_body(squat, performed_at=DAY.isoformat())

    created = logged_in_client.put(path, json=body)
    replaced = logged_in_client.put(path, json=body | {"reps": 4, "weight": 102.5})

    assert created.status_code == 201, created.text
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["id"] == created.json()["id"]
    assert (replaced.json()["reps"], replaced.json()["weight"]) == (4, "102.50")
    assert record_count(db_session, user_id=current_user.id) == 1


def test_repeating_the_same_put_leaves_one_record(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    path = f"/api/set-records/{uuid.uuid4()}"

    responses = [logged_in_client.put(path, json=record_body(squat)) for _ in range(3)]

    assert [response.status_code for response in responses] == [201, 200, 200]
    assert len({response.json()["performed_at"] for response in responses}) == 1
    assert record_count(db_session, user_id=current_user.id) == 1


def test_put_defaults_to_the_preferred_unit_and_now(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()
    started = now()

    body = logged_in_client.put(f"/api/set-records/{uuid.uuid4()}", json=record_body(squat)).json()

    assert body["weight_unit"] == "lb"
    assert body["exercise_id"] == str(squat.id)
    performed_at = datetime.fromisoformat(body["performed_at"])
    assert started - timedelta(seconds=5) <= performed_at <= now() + timedelta(seconds=5)


def test_replacing_can_move_the_record_in_time(
    logged_in_client: TestClient, squat: Exercise
) -> None:
    path = f"/api/set-records/{uuid.uuid4()}"
    logged_in_client.put(path, json=record_body(squat, performed_at=DAY.isoformat()))
    later = DAY + timedelta(hours=1)

    body = logged_in_client.put(path, json=record_body(squat, performed_at=later.isoformat()))

    assert datetime.fromisoformat(body.json()["performed_at"]) == later


def test_another_users_record_id_is_a_409(
    logged_in_client: TestClient, db_session: Session, squat: Exercise
) -> None:
    theirs = create_set_record(db_session, user=create_user(db_session), exercise=squat, reps=8)

    response = logged_in_client.put(f"/api/set-records/{theirs.id}", json=record_body(squat))

    assert_error(response, 409, "id_conflict")
    db_session.expire_all()
    assert db_session.get(SetRecord, theirs.id).reps == 8


def test_only_visible_exercises_can_be_logged(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))
    own = create_exercise(db_session, owner=current_user)

    for exercise_id in [theirs.id, uuid.uuid4()]:
        response = logged_in_client.put(
            f"/api/set-records/{uuid.uuid4()}",
            json={"exercise_id": str(exercise_id), "reps": 5, "weight": "100"},
        )
        assert_error(response, 422, "invalid")
    own_response = logged_in_client.put(f"/api/set-records/{uuid.uuid4()}", json=record_body(own))

    assert own_response.status_code == 201
    assert record_count(db_session, user_id=current_user.id) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"reps": -1},
        {"reps": 1001},
        {"weight": "-0.5"},
        {"weight": "100.125"},
        {"weight": "10000"},
        {"weight_unit": "stone"},
        {"performed_at": "2026-11-02T18:00:00"},
        {"reps": None},
    ],
)
def test_invalid_records_are_rejected(
    logged_in_client: TestClient, db_session: Session, squat: Exercise, change: dict
) -> None:
    response = logged_in_client.put(
        f"/api/set-records/{uuid.uuid4()}", json=record_body(squat) | change
    )

    assert_error(response, 422, "invalid")
    assert record_count(db_session) == 0


def test_a_failed_attempt_with_zero_reps_can_be_logged(
    logged_in_client: TestClient, squat: Exercise
) -> None:
    response = logged_in_client.put(
        f"/api/set-records/{uuid.uuid4()}", json=record_body(squat, reps=0)
    )

    assert response.status_code == 201, response.text
    assert response.json()["reps"] == 0


# Show and delete


def test_showing_and_deleting_own_records(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    record = create_set_record(db_session, user=current_user, exercise=squat)
    path = f"/api/set-records/{record.id}"
    # As a real request would, read the stored NUMERIC(6, 2) value rather than the factory's
    db_session.expire_all()

    shown = logged_in_client.get(path)
    deleted = logged_in_client.delete(path)

    assert shown.status_code == 200
    assert shown.json()["weight"] == "60.00"
    assert deleted.status_code == 204
    assert_error(logged_in_client.get(path), 404, "not_found")


def test_another_users_record_is_not_found(
    logged_in_client: TestClient, db_session: Session, squat: Exercise
) -> None:
    theirs = create_set_record(db_session, user=create_user(db_session), exercise=squat)
    path = f"/api/set-records/{theirs.id}"

    assert_error(logged_in_client.get(path), 404, "not_found")
    assert_error(logged_in_client.delete(path), 404, "not_found")
    assert record_count(db_session, id=theirs.id) == 1


# History


@pytest.fixture
def week(db_session: Session, current_user: User, squat: Exercise) -> list[SetRecord]:
    """One squat record a day for a week, oldest first, plus records that aren't in this
    user's squat history"""
    records = [
        create_set_record(
            db_session,
            user=current_user,
            exercise=squat,
            reps=day + 1,
            performed_at=DAY + timedelta(days=day),
        )
        for day in range(7)
    ]
    create_set_record(db_session, user=create_user(db_session), exercise=squat, performed_at=DAY)
    create_set_record(db_session, user=current_user, performed_at=DAY)
    return records


def reps(body: dict) -> list[int]:
    return [item["reps"] for item in body["items"]]


@pytest.mark.usefixtures("week")
def test_history_is_newest_first_and_only_the_users_own(
    logged_in_client: TestClient, squat: Exercise
) -> None:
    body = logged_in_client.get(history_path(squat)).json()

    assert reps(body) == [7, 6, 5, 4, 3, 2, 1]
    assert body["total"] == 7


@pytest.mark.usefixtures("week")
def test_history_is_filtered_by_date_range(logged_in_client: TestClient, squat: Exercise) -> None:
    params = {
        "since": (DAY + timedelta(days=2)).isoformat(),
        "until": (DAY + timedelta(days=5)).isoformat(),
    }

    body = logged_in_client.get(history_path(squat), params=params).json()

    # since is inclusive, until is not
    assert reps(body) == [5, 4, 3]
    assert body["total"] == 3


@pytest.mark.usefixtures("week")
def test_history_pages_backwards_with_before(logged_in_client: TestClient, squat: Exercise) -> None:
    pages = []
    params: dict[str, object] = {"limit": 3}
    while True:
        body = logged_in_client.get(history_path(squat), params=params).json()
        if not body["items"]:
            break
        pages.append(reps(body))
        params = {"limit": 3, "before": body["items"][-1]["performed_at"]}

    assert pages == [[7, 6, 5], [4, 3, 2], [1]]


def test_a_page_never_splits_records_logged_at_the_same_time(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    for count in [1, 2, 3, 4]:
        create_set_record(
            db_session, user=current_user, exercise=squat, reps=count, performed_at=DAY
        )
    create_set_record(
        db_session, user=current_user, exercise=squat, reps=9, performed_at=DAY - timedelta(days=1)
    )

    first = logged_in_client.get(history_path(squat), params={"limit": 2}).json()
    second = logged_in_client.get(
        history_path(squat), params={"limit": 2, "before": first["items"][-1]["performed_at"]}
    ).json()

    assert sorted(reps(first)) == [1, 2, 3, 4]
    assert reps(second) == [9]


def test_history_of_an_invisible_exercise_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))

    assert_error(logged_in_client.get(history_path(theirs)), 404, "not_found")
    assert_error(logged_in_client.get(f"{history_path(theirs)}/new"), 404, "not_found")


def test_history_dates_need_a_timezone(logged_in_client: TestClient, squat: Exercise) -> None:
    response = logged_in_client.get(history_path(squat), params={"since": "2026-11-02T18:00:00"})

    assert_error(response, 422, "invalid")


# The logging form


def test_new_suggests_the_latest_record(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    create_set_record(
        db_session,
        user=current_user,
        exercise=squat,
        reps=5,
        weight=Decimal("100"),
        performed_at=DAY + timedelta(days=1),
    )
    create_set_record(
        db_session,
        user=current_user,
        exercise=squat,
        reps=3,
        weight=Decimal("110"),
        weight_unit=WeightUnit.LB,
        performed_at=DAY,
    )

    response = logged_in_client.get(f"{history_path(squat)}/new")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "defaults": {"reps": 5, "weight": "100.00", "weight_unit": "kg"},
        "options": {"weight_unit": ["kg", "lb"]},
    }


def test_new_without_history_offers_the_preferred_unit(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()
    create_set_record(db_session, user=create_user(db_session), exercise=squat)

    defaults = logged_in_client.get(f"{history_path(squat)}/new").json()["defaults"]

    assert defaults == {"reps": None, "weight": None, "weight_unit": "lb"}


def test_set_records_need_a_login(client: TestClient, squat: Exercise) -> None:
    assert_error(client.get(history_path(squat)), 401, "not_authenticated")
    assert_error(
        client.put(f"/api/set-records/{uuid.uuid4()}", json=record_body(squat)),
        401,
        "not_authenticated",
    )
