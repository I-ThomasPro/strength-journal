"""Server-side sessions: the cookie holds a random token, the database holds its hash.

- Sessions last `session_days` (30) and the expiry moves forward on use, at most hourly
- Logged-in unsafe requests (POST/PUT/PATCH/DELETE) must send the session's CSRF token in
  the X-CSRF-Token header
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.auth.security import hash_token, new_token, tokens_match
from app.config import get_settings
from app.db import DbSession
from app.models.user import User
from app.models.user_session import UserSession

CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
REFRESH_AFTER = timedelta(hours=1)


def now() -> datetime:
    return datetime.now(UTC)


def _lifetime() -> timedelta:
    return timedelta(days=get_settings().session_days)


def start_session(db: Session, user: User) -> tuple[UserSession, str]:
    """Create a session for the user; returns it and the token to put in the cookie"""
    token = new_token()
    current = now()
    session = UserSession(
        user=user,
        token_hash=hash_token(token),
        csrf_token=new_token(),
        expires_at=current + _lifetime(),
        last_seen_at=current,
    )
    db.add(session)
    db.flush()
    return session, token


def find_session(db: Session, token: str | None) -> UserSession | None:
    """The unexpired session for a cookie token, if any"""
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.expires_at <= now():
        return None
    return session


def refresh_if_due(session: UserSession) -> bool:
    """Move the expiry forward on use, at most hourly; True if it moved"""
    current = now()
    if current - session.last_seen_at < REFRESH_AFTER:
        return False
    session.last_seen_at = current
    session.expires_at = current + _lifetime()
    return True


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=int(_lifetime().total_seconds()),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def not_authenticated() -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "You're not logged in")


def get_current_session(request: Request, response: Response, db: DbSession) -> UserSession:
    """The logged-in session: 401 without one, 403 on an unsafe request without its CSRF token"""
    token = request.cookies.get(get_settings().session_cookie_name)
    session = find_session(db, token)
    if session is None or token is None:
        raise not_authenticated()
    if request.method not in SAFE_METHODS and not tokens_match(
        request.headers.get(CSRF_HEADER), session.csrf_token
    ):
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "csrf_failed", f"Missing or wrong {CSRF_HEADER} header"
        )
    if refresh_if_due(session):
        set_session_cookie(response, token)
    return session


CurrentSession = Annotated[UserSession, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]
