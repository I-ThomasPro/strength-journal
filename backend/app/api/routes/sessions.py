import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app.api.errors import not_found
from app.api.pagination import PageQuery, paginate
from app.auth.sessions import CurrentSession, clear_session_cookie, now
from app.db import DbSession
from app.models.user_session import UserSession
from app.schemas.auth import UserSessionRead
from app.schemas.common import Page

# The user's logins on every device. The current login alone is the singular `session`
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def index(current: CurrentSession, db: DbSession, page: PageQuery) -> Page[UserSessionRead]:
    """The user's unexpired sessions, most recently used first"""
    statement = (
        select(UserSession)
        .where(UserSession.user_id == current.user_id, UserSession.expires_at > now())
        .order_by(UserSession.last_seen_at.desc(), UserSession.id)
    )
    sessions, total = paginate(db, statement, page)
    items = [
        UserSessionRead(
            id=session.id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
            current=session.id == current.id,
        )
        for session in sessions
    ]
    return Page(items=items, total=total)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, current: CurrentSession, db: DbSession, response: Response) -> None:
    """Log a device out. For the current session, this is the same as `DELETE /api/session`"""
    session = db.get(UserSession, id)
    if session is None or session.user_id != current.user_id or session.expires_at <= now():
        raise not_found()
    db.delete(session)
    if session.id == current.id:
        clear_session_cookie(response)
