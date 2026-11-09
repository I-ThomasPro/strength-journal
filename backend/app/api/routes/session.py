from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.errors import ApiError
from app.auth.security import verify_dummy_password, verify_password
from app.auth.sessions import (
    CurrentSession,
    clear_session_cookie,
    set_session_cookie,
    start_session,
)
from app.db import DbSession
from app.models.user import User
from app.schemas.auth import SessionCreate, SessionRead, UserRead

# A singular resource: the current login (see app/api/restful.py)
router = APIRouter(prefix="/session", tags=["session"])


def invalid_credentials() -> ApiError:
    return ApiError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Wrong email or password")


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: SessionCreate, db: DbSession, response: Response) -> SessionRead:
    """Log in. A wrong email and a wrong password get the same response"""
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        verify_dummy_password(body.password)
        raise invalid_credentials()
    if not verify_password(body.password, user.password_hash):
        raise invalid_credentials()
    session, token = start_session(db, user)
    set_session_cookie(response, token)
    return SessionRead(user=UserRead.model_validate(user), csrf_token=session.csrf_token)


@router.get("")
def show(session: CurrentSession) -> SessionRead:
    """The logged-in user and the session's CSRF token"""
    return SessionRead(user=UserRead.model_validate(session.user), csrf_token=session.csrf_token)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def destroy(session: CurrentSession, db: DbSession, response: Response) -> None:
    """Log out of this device"""
    db.delete(session)
    clear_session_cookie(response)
