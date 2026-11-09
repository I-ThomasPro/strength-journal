from fastapi import APIRouter, Depends, Response, status

from app.auth.invites import claim_invite, mark_used
from app.auth.security import hash_password
from app.auth.sessions import require_csrf_if_logged_in, set_session_cookie, start_session
from app.db import DbSession
from app.models.user import User
from app.schemas.auth import RegistrationCreate, SessionRead, UserRead

# A singular resource: signing up (see app/api/restful.py)
router = APIRouter(prefix="/registration", tags=["registration"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf_if_logged_in)],
)
def create(body: RegistrationCreate, db: DbSession, response: Response) -> SessionRead:
    """Sign up with an invite code; logs the new user in"""
    # The invite first: without a valid one, nothing else (e.g. whether the email is taken)
    # is checked or revealed
    invite = claim_invite(db, body.invite_code)
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        weight_unit=body.weight_unit,
    )
    db.add(user)
    # A taken email fails here (409 duplicate_email); the rollback leaves the invite unused
    db.flush()
    mark_used(invite, user)
    session, token = start_session(db, user)
    set_session_cookie(response, token)
    return SessionRead(user=UserRead.model_validate(user), csrf_token=session.csrf_token)
