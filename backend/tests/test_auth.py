"""Sign-up, login, logout, sessions, CSRF and the request guards"""

from collections.abc import Callable
from contextlib import nullcontext
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.auth.invites import create_invite
from app.auth.security import hash_password, hash_token, verify_password
from app.auth.sessions import CSRF_HEADER, now, start_session
from app.config import get_settings
from app.models.invite import Invite
from app.models.user import User
from app.models.user_session import UserSession
from tests.factories import create_user
from tests.helpers import TEST_PASSWORD, assert_error

COOKIE = get_settings().session_cookie_name


def registration(code: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "invite_code": code,
        "username": "New.Lifter",
        "password": "a long enough password",
        "display_name": "New Lifter",
    }
    return body | overrides


def invite_for(db_session: Session, code: str) -> Invite:
    db_session.expire_all()
    return db_session.scalars(select(Invite).where(Invite.code_hash == hash_token(code))).one()


# Registration


def test_signing_up_with_a_valid_invite_creates_the_user_and_logs_in(
    client: TestClient, db_session: Session
) -> None:
    code = create_invite(db_session)

    response = client.post("/api/registration", json=registration(code, weight_unit="lb"))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["username"] == "new.lifter"
    assert body["user"]["weight_unit"] == "lb"
    assert body["csrf_token"]
    user = db_session.scalars(select(User).where(User.username == "new.lifter")).one()
    assert verify_password("a long enough password", user.password_hash)
    invite = invite_for(db_session, code)
    assert invite.used_at is not None and invite.used_by_id == user.id
    # The new session works straight away
    assert client.get("/api/session").json()["user"]["id"] == str(user.id)


def test_an_invite_can_only_be_used_once(client: TestClient, db_session: Session) -> None:
    code = create_invite(db_session)
    client.post("/api/registration", json=registration(code))
    client.cookies.clear()

    response = client.post("/api/registration", json=registration(code, username="another.lifter"))

    assert_error(response, 422, "invalid_invite")


def test_an_expired_invite_is_rejected(client: TestClient, db_session: Session) -> None:
    code = create_invite(db_session)
    invite_for(db_session, code).expires_at = now() - timedelta(minutes=1)
    db_session.flush()

    assert_error(client.post("/api/registration", json=registration(code)), 422, "invalid_invite")


def test_an_unknown_invite_is_rejected(client: TestClient) -> None:
    response = client.post("/api/registration", json=registration("no-such-code"))

    assert_error(response, 422, "invalid_invite")


def test_a_taken_username_is_a_409_and_leaves_the_invite_unused(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="taken")
    code = create_invite(db_session)

    response = client.post("/api/registration", json=registration(code, username=" Taken "))

    assert_error(response, 409, "duplicate_username")
    assert invite_for(db_session, code).used_at is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("password", "too short"),
        ("username", "ab"),
        ("username", "x" * 33),
        ("username", "two words"),
        ("username", "lifter@example.com"),
        ("display_name", "   "),
        ("weight_unit", "stone"),
    ],
)
def test_invalid_sign_up_fields_are_rejected(
    client: TestClient, db_session: Session, field: str, value: str
) -> None:
    code = create_invite(db_session)

    response = client.post("/api/registration", json=registration(code, **{field: value}))

    assert_error(response, 422, "invalid")


# Logging in and out


def test_logging_in_starts_a_session(
    client: TestClient, current_user: User, db_session: Session
) -> None:
    response = client.post(
        "/api/session", json={"username": current_user.username.upper(), "password": TEST_PASSWORD}
    )

    assert response.status_code == 201, response.text
    cookie = response.headers["set-cookie"].lower()
    assert f"{COOKIE}=" in cookie
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
    assert response.json()["user"]["id"] == str(current_user.id)
    assert client.get("/api/session").status_code == 200


def test_a_username_carried_over_from_an_email_still_logs_in(
    client: TestClient, db_session: Session
) -> None:
    create_user(
        db_session, username="old.lifter@example.com", password_hash=hash_password(TEST_PASSWORD)
    )

    response = client.post(
        "/api/session", json={"username": " Old.Lifter@Example.com ", "password": TEST_PASSWORD}
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["username"] == "old.lifter@example.com"


def test_a_wrong_username_and_a_wrong_password_get_the_same_response(
    client: TestClient, current_user: User
) -> None:
    wrong_password = client.post(
        "/api/session", json={"username": current_user.username, "password": "not the password"}
    )
    wrong_username = client.post(
        "/api/session", json={"username": "nobody", "password": TEST_PASSWORD}
    )

    assert_error(wrong_password, 401, "invalid_credentials")
    assert wrong_password.json()["detail"] == "Wrong username or password"
    assert (wrong_username.status_code, wrong_username.json()) == (
        wrong_password.status_code,
        wrong_password.json(),
    )
    assert "set-cookie" not in wrong_password.headers


def test_showing_the_session_returns_the_user_and_csrf_token(
    logged_in_client: TestClient, current_user: User
) -> None:
    body = logged_in_client.get("/api/session").json()

    assert body["user"] == {
        "id": str(current_user.id),
        "username": current_user.username,
        "display_name": current_user.display_name,
        "weight_unit": "kg",
        "is_admin": False,
    }
    assert body["csrf_token"] == logged_in_client.headers[CSRF_HEADER]


def test_logging_out_ends_the_session(logged_in_client: TestClient, db_session: Session) -> None:
    response = logged_in_client.delete("/api/session")

    assert response.status_code == 204
    assert f"{COOKIE}=" in response.headers["set-cookie"]
    db_session.expire_all()
    assert db_session.scalars(select(UserSession)).all() == []
    assert_error(logged_in_client.get("/api/session"), 401, "not_authenticated")


def test_without_a_session_you_are_not_authenticated(client: TestClient) -> None:
    assert_error(client.get("/api/session"), 401, "not_authenticated")
    client.cookies.set(COOKIE, "not-a-real-token")
    assert_error(client.get("/api/session"), 401, "not_authenticated")


def test_an_expired_session_is_not_authenticated(
    client: TestClient, db_session: Session, current_user: User
) -> None:
    session, token = start_session(db_session, current_user)
    session.expires_at = now() - timedelta(seconds=1)
    db_session.flush()
    client.cookies.set(COOKIE, token)

    assert_error(client.get("/api/session"), 401, "not_authenticated")


def test_the_expiry_moves_forward_on_use_at_most_hourly(
    client: TestClient, db_session: Session, current_user: User
) -> None:
    session, token = start_session(db_session, current_user)
    client.cookies.set(COOKIE, token)

    # Used within the hour: no change and no new cookie
    original_expiry = session.expires_at
    recent = client.get("/api/session")
    db_session.refresh(session)
    assert session.expires_at == original_expiry
    assert "set-cookie" not in recent.headers

    # Last used two hours ago, expiring tomorrow: moved forward to the full 30 days
    session.last_seen_at = now() - timedelta(hours=2)
    session.expires_at = now() + timedelta(days=1)
    db_session.flush()
    stale = client.get("/api/session")
    db_session.refresh(session)
    assert session.expires_at > now() + timedelta(days=get_settings().session_days - 1)
    assert f"{COOKIE}=" in stale.headers["set-cookie"]


def test_deleting_a_user_deletes_their_sessions(db_session: Session, current_user: User) -> None:
    session, _ = start_session(db_session, current_user)
    session_id = session.id

    db_session.delete(current_user)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(UserSession, session_id) is None


# CSRF and the request guards


def test_an_unsafe_request_without_the_csrf_token_is_rejected(
    logged_in_client: TestClient,
) -> None:
    del logged_in_client.headers[CSRF_HEADER]

    assert_error(logged_in_client.delete("/api/session"), 403, "csrf_failed")


def test_an_unsafe_request_with_a_wrong_csrf_token_is_rejected(
    logged_in_client: TestClient,
) -> None:
    logged_in_client.headers[CSRF_HEADER] = "wrong"

    assert_error(logged_in_client.delete("/api/session"), 403, "csrf_failed")


def test_safe_requests_dont_need_the_csrf_token(logged_in_client: TestClient) -> None:
    del logged_in_client.headers[CSRF_HEADER]

    assert logged_in_client.get("/api/session").status_code == 200


def test_unsafe_requests_from_another_origin_are_rejected(
    client: TestClient, current_user: User
) -> None:
    body = {"username": current_user.username, "password": TEST_PASSWORD}
    allowed = {"Origin": get_settings().allowed_origin}

    response = client.post("/api/session", json=body, headers={"Origin": "https://evil.example"})

    assert_error(response, 403, "bad_origin")
    assert client.post("/api/session", json=body, headers=allowed).status_code == 201


def test_unsafe_requests_must_send_json(client: TestClient, current_user: User) -> None:
    response = client.post(
        "/api/session", data={"username": current_user.username, "password": TEST_PASSWORD}
    )

    assert_error(response, 415, "unsupported_media_type")


def test_the_password_hash_never_appears_in_responses(
    client: TestClient, db_session: Session, current_user: User
) -> None:
    code = create_invite(db_session)
    responses = [
        client.post(
            "/api/session", json={"username": current_user.username, "password": TEST_PASSWORD}
        ),
        client.get("/api/session"),
    ]
    # Sign up as someone else, logged out (logged in, it would need the CSRF token)
    client.cookies.clear()
    responses.append(client.post("/api/registration", json=registration(code)))

    for response in responses:
        assert response.status_code < 300, response.text
        assert "password" not in response.text
        assert current_user.password_hash not in response.text


# Invites from the command line


def test_create_invite_command_prints_a_working_code(
    client: TestClient, db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    session_factory: Callable[[], nullcontext[Session]] = lambda: nullcontext(db_session)  # noqa: E731

    assert cli.main(["create-invite", "--days", "3"], session_factory=session_factory) == 0

    code = capsys.readouterr().out.strip().rsplit(" ", 1)[-1]
    invite = invite_for(db_session, code)
    assert timedelta(days=2, hours=23) < invite.expires_at - now() <= timedelta(days=3)
    assert client.post("/api/registration", json=registration(code)).status_code == 201


# Review fixes: no username enumeration, CSRF on login and sign-up, no echoed secrets


def test_an_invalid_invite_doesnt_reveal_whether_a_username_is_taken(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, username="taken")

    taken = client.post("/api/registration", json=registration("no-such-code", username="taken"))
    free = client.post("/api/registration", json=registration("no-such-code", username="free"))

    assert_error(taken, 422, "invalid_invite")
    assert (taken.status_code, taken.json()) == (free.status_code, free.json())


@pytest.mark.parametrize("path", ["/api/session", "/api/registration"])
def test_logging_in_or_signing_up_while_logged_in_needs_the_csrf_token(
    logged_in_client: TestClient, db_session: Session, current_user: User, path: str
) -> None:
    body = (
        {"username": current_user.username, "password": TEST_PASSWORD}
        if path == "/api/session"
        else registration(create_invite(db_session))
    )
    token = logged_in_client.headers.pop(CSRF_HEADER)

    assert_error(logged_in_client.post(path, json=body), 403, "csrf_failed")
    assert logged_in_client.post(path, json=body, headers={CSRF_HEADER: token}).status_code == 201


def test_logging_in_without_a_session_needs_no_csrf_token(
    client: TestClient, current_user: User
) -> None:
    client.cookies.set(COOKIE, "an-expired-or-unknown-token")

    response = client.post(
        "/api/session", json={"username": current_user.username, "password": TEST_PASSWORD}
    )

    assert response.status_code == 201


def test_validation_errors_dont_echo_passwords_or_invite_codes(
    client: TestClient, db_session: Session
) -> None:
    code = create_invite(db_session)
    short_password = client.post("/api/registration", json=registration(code, password="secret-9"))
    missing_password = client.post(
        "/api/registration",
        json={k: v for k, v in registration(code).items() if k != "password"},
    )
    missing_username = client.post("/api/session", json={"password": "my real password"})

    assert_error(short_password, 422, "invalid")
    assert "secret-9" not in short_password.text
    assert_error(missing_password, 422, "invalid")
    assert code not in missing_password.text
    assert_error(missing_username, 422, "invalid")
    assert "my real password" not in missing_username.text
