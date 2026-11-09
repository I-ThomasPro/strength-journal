"""Shared test helpers"""

from typing import Any

from httpx import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

# The password of the `current_user` fixture
TEST_PASSWORD = "correct horse battery staple"


def check_deferred_constraints(session: Session) -> None:
    """Position uniqueness is checked at commit; force the check now (tests never commit)"""
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def assert_error(response: Response, status_code: int, code: str) -> dict[str, Any]:
    """Assert an error response in the API's format; returns its body"""
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["code"] == code, body
    assert isinstance(body["detail"], str) and body["detail"]
    return body
