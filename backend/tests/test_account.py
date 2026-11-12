"""The logged-in user's profile, password and sessions on other devices"""

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.auth.sessions import now, start_session
from app.config import get_settings
from app.main import app
from app.models.user import User
from app.models.user_session import UserSession
from tests.factories import create_user
from tests.helpers import TEST_PASSWORD, assert_error

COOKIE = get_settings().session_cookie_name
NEW_PASSWORD = "a brand new password"


def other_device(
    client_for: Callable[[FastAPI], TestClient], db_session: Session, user: User
) -> tuple[TestClient, UserSession]:
    """A second client, logged in as `user` with its own session"""
    session, token = start_session(db_session, user)
    device = client_for(app)
    device.cookies.set(COOKIE, token)
    return device, session


# Profile


def test_showing_the_profile(logged_in_client: TestClient, current_user: User) -> None:
    response = logged_in_client.get("/api/profile")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(current_user.id),
        "username": current_user.username,
        "display_name": current_user.display_name,
        "weight_unit": "kg",
    }


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"display_name": "  Heavy Lifter  "}, {"display_name": "Heavy Lifter"}),
        ({"weight_unit": "lb"}, {"weight_unit": "lb"}),
    ],
)
def test_each_profile_field_updates_on_its_own(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    change: dict[str, str],
    expected: dict[str, str],
) -> None:
    before = logged_in_client.get("/api/profile").json()

    response = logged_in_client.patch("/api/profile", json=change)

    assert response.status_code == 200, response.text
    assert response.json() == before | expected
    db_session.refresh(current_user)
    assert {field: getattr(current_user, field) for field in expected} == expected


def test_an_empty_profile_update_changes_nothing(logged_in_client: TestClient) -> None:
    before = logged_in_client.get("/api/profile").json()

    response = logged_in_client.patch("/api/profile", json={})

    assert response.status_code == 200
    assert response.json() == before


@pytest.mark.parametrize(
    "change",
    [
        {"weight_unit": "stone"},
        {"weight_unit": None},
        {"display_name": "   "},
        {"display_name": None},
        {"display_name": "x" * 101},
    ],
)
def test_invalid_profile_changes_are_rejected(
    logged_in_client: TestClient, change: dict[str, object]
) -> None:
    assert_error(logged_in_client.patch("/api/profile", json=change), 422, "invalid")


def test_the_username_cant_be_changed_through_the_profile(
    logged_in_client: TestClient, current_user: User
) -> None:
    username = current_user.username

    response = logged_in_client.patch("/api/profile", json={"username": "new-name"})

    assert response.status_code == 200
    assert response.json()["username"] == username


def test_the_profile_needs_a_login(client: TestClient) -> None:
    assert_error(client.get("/api/profile"), 401, "not_authenticated")


# Password


def test_changing_the_password(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    body = {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}

    response = logged_in_client.patch("/api/password", json=body)

    assert response.status_code == 204, response.text
    db_session.refresh(current_user)
    assert verify_password(NEW_PASSWORD, current_user.password_hash)
    assert not verify_password(TEST_PASSWORD, current_user.password_hash)


def test_a_wrong_current_password_is_rejected(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    body = {"current_password": "not my password", "new_password": NEW_PASSWORD}

    assert_error(logged_in_client.patch("/api/password", json=body), 401, "invalid_credentials")
    db_session.refresh(current_user)
    assert verify_password(TEST_PASSWORD, current_user.password_hash)
    # Still logged in
    assert logged_in_client.get("/api/profile").status_code == 200


def test_the_new_password_follows_the_sign_up_rules(logged_in_client: TestClient) -> None:
    body = {"current_password": TEST_PASSWORD, "new_password": "too-short"}

    response = logged_in_client.patch("/api/password", json=body)

    assert_error(response, 422, "invalid")
    assert "too-short" not in response.text
    assert TEST_PASSWORD not in response.text


def test_changing_the_password_logs_out_other_devices_only(
    logged_in_client: TestClient,
    client_for: Callable[[FastAPI], TestClient],
    db_session: Session,
    current_user: User,
) -> None:
    device, _ = other_device(client_for, db_session, current_user)
    someone_else, _ = other_device(client_for, db_session, create_user(db_session))
    body = {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}

    assert logged_in_client.patch("/api/password", json=body).status_code == 204

    assert_error(device.get("/api/profile"), 401, "not_authenticated")
    assert logged_in_client.get("/api/profile").status_code == 200
    assert someone_else.get("/api/profile").status_code == 200


def test_changing_the_password_needs_the_csrf_token(logged_in_client: TestClient) -> None:
    del logged_in_client.headers["X-CSRF-Token"]
    body = {"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD}

    assert_error(logged_in_client.patch("/api/password", json=body), 403, "csrf_failed")


def test_logging_in_with_the_new_password(
    client: TestClient, db_session: Session, current_user: User
) -> None:
    current_user.password_hash = hash_password(NEW_PASSWORD)
    db_session.flush()

    old = client.post(
        "/api/session", json={"username": current_user.username, "password": TEST_PASSWORD}
    )
    new = client.post(
        "/api/session", json={"username": current_user.username, "password": NEW_PASSWORD}
    )

    assert_error(old, 401, "invalid_credentials")
    assert new.status_code == 201


# Sessions on other devices


def test_listing_sessions_marks_the_current_one(
    logged_in_client: TestClient,
    client_for: Callable[[FastAPI], TestClient],
    db_session: Session,
    current_user: User,
) -> None:
    _, other = other_device(client_for, db_session, current_user)
    other.last_seen_at = now() - timedelta(days=2)
    expired, _ = start_session(db_session, current_user)
    expired.expires_at = now() - timedelta(seconds=1)
    start_session(db_session, create_user(db_session))
    db_session.flush()

    response = logged_in_client.get("/api/sessions")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    current, previous = body["items"]
    assert current["current"] is True
    assert previous == {
        "id": str(other.id),
        "created_at": other.created_at.isoformat().replace("+00:00", "Z"),
        "last_seen_at": other.last_seen_at.isoformat().replace("+00:00", "Z"),
        "current": False,
    }


def test_deleting_a_session_logs_that_device_out(
    logged_in_client: TestClient,
    client_for: Callable[[FastAPI], TestClient],
    db_session: Session,
    current_user: User,
) -> None:
    device, other = other_device(client_for, db_session, current_user)
    assert device.get("/api/profile").status_code == 200

    response = logged_in_client.delete(f"/api/sessions/{other.id}")

    assert response.status_code == 204
    assert "set-cookie" not in response.headers
    assert_error(device.get("/api/profile"), 401, "not_authenticated")
    assert logged_in_client.get("/api/profile").status_code == 200


def test_deleting_the_current_session_logs_this_device_out(logged_in_client: TestClient) -> None:
    current = logged_in_client.get("/api/sessions").json()["items"][0]

    response = logged_in_client.delete(f"/api/sessions/{current['id']}")

    assert response.status_code == 204
    assert f"{COOKIE}=" in response.headers["set-cookie"]
    assert_error(logged_in_client.get("/api/profile"), 401, "not_authenticated")


def test_another_users_session_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs, _ = start_session(db_session, create_user(db_session))

    assert_error(logged_in_client.delete(f"/api/sessions/{theirs.id}"), 404, "not_found")
    db_session.expire_all()
    assert db_session.scalar(select(UserSession).where(UserSession.id == theirs.id)) is not None


def test_sessions_need_a_login(client: TestClient) -> None:
    assert_error(client.get("/api/sessions"), 401, "not_authenticated")
