"""Admins creating accounts with POST /api/users"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from tests.factories import create_user
from tests.helpers import assert_error

NEW_PASSWORD = "a long enough password"


def new_account(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "username": "New.Lifter",
        "display_name": "New Lifter",
        "password": NEW_PASSWORD,
    }
    return body | overrides


@pytest.fixture
def admin_client(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> TestClient:
    """`logged_in_client`, with `current_user` made an admin"""
    current_user.is_admin = True
    db_session.flush()
    return logged_in_client


def test_an_admin_creates_an_account_that_can_log_in(
    admin_client: TestClient, db_session: Session
) -> None:
    response = admin_client.post("/api/users", json=new_account(weight_unit="lb"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body | {"id": None} == {
        "id": None,
        "username": "new.lifter",
        "display_name": "New Lifter",
        "weight_unit": "lb",
        "is_admin": False,
    }
    assert "password" not in response.text
    # The admin stays logged in as themselves; the new account logs in on its own
    admin_client.cookies.clear()
    login = admin_client.post(
        "/api/session", json={"username": "New.Lifter", "password": NEW_PASSWORD}
    )
    assert login.status_code == 201, login.text
    assert login.json()["user"]["id"] == body["id"]


def test_an_admin_can_create_another_admin(admin_client: TestClient, db_session: Session) -> None:
    response = admin_client.post("/api/users", json=new_account(is_admin=True))

    assert response.status_code == 201, response.text
    assert response.json()["is_admin"] is True
    db_session.expire_all()
    assert db_session.scalars(select(User.is_admin).where(User.username == "new.lifter")).one()


def test_others_cant_create_accounts(
    logged_in_client: TestClient, client: TestClient, db_session: Session
) -> None:
    assert_error(logged_in_client.post("/api/users", json=new_account()), 403, "admin_only")
    logged_in_client.cookies.clear()
    assert_error(client.post("/api/users", json=new_account()), 401, "not_authenticated")
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.username == "new.lifter")) is None


def test_a_taken_username_is_a_409(admin_client: TestClient, db_session: Session) -> None:
    create_user(db_session, username="taken")

    response = admin_client.post("/api/users", json=new_account(username=" Taken "))

    assert_error(response, 409, "duplicate_username")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "ab"),
        ("username", "two words"),
        ("password", "too short"),
        ("display_name", "   "),
        ("weight_unit", "stone"),
    ],
)
def test_invalid_fields_are_rejected(admin_client: TestClient, field: str, value: str) -> None:
    response = admin_client.post("/api/users", json=new_account(**{field: value}))

    assert_error(response, 422, "invalid")
    assert [error["loc"] for error in response.json()["errors"]] == [["body", field]]
    assert NEW_PASSWORD not in response.text
