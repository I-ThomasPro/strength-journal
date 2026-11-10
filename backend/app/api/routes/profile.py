from fastapi import APIRouter

from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.schemas.auth import ProfileUpdate, UserRead

# A singular resource: the logged-in user's settings (see app/api/restful.py)
router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def show(user: CurrentUser) -> UserRead:
    """The logged-in user's profile"""
    return UserRead.model_validate(user)


@router.patch("")
def update(body: ProfileUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    """Change the display name or weight unit; fields left out stay as they are"""
    body.apply_to(user)
    db.flush()
    return UserRead.model_validate(user)
