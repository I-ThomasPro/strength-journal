from fastapi import APIRouter, status
from sqlalchemy import delete

from app.auth.security import hash_password, verify_password
from app.auth.sessions import CurrentSession, invalid_credentials
from app.db import DbSession
from app.models.user_session import UserSession
from app.schemas.auth import PasswordUpdate

# A singular resource: the logged-in user's password (see app/api/restful.py)
router = APIRouter(prefix="/password", tags=["password"])


@router.patch("", status_code=status.HTTP_204_NO_CONTENT)
def update(body: PasswordUpdate, session: CurrentSession, db: DbSession) -> None:
    """Change the password and log out every other device; this one stays logged in"""
    user = session.user
    if not verify_password(body.current_password, user.password_hash):
        raise invalid_credentials("Your current password is wrong")
    user.password_hash = hash_password(body.new_password)
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.id != session.id)
    )
