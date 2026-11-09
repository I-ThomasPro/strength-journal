from fastapi import APIRouter, Response, status

from app.auth.invites import redeem_invite
from app.auth.security import hash_password
from app.auth.sessions import set_session_cookie, start_session
from app.db import DbSession
from app.models.user import User
from app.schemas.auth import RegistrationCreate, SessionRead, UserRead

# A singular resource: signing up (see app/api/restful.py)
router = APIRouter(prefix="/registration", tags=["registration"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: RegistrationCreate, db: DbSession, response: Response) -> SessionRead:
    """Sign up with an invite code; logs the new user in"""
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        weight_unit=body.weight_unit,
    )
    db.add(user)
    # A taken email fails here (409 duplicate_email) and rolls back, leaving the invite unused
    db.flush()
    redeem_invite(db, body.invite_code, user)
    session, token = start_session(db, user)
    set_session_cookie(response, token)
    return SessionRead(user=UserRead.model_validate(user), csrf_token=session.csrf_token)
