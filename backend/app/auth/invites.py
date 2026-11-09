"""Single-use invite codes for signing up. Only the code's hash is stored"""

from datetime import timedelta

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.auth.security import hash_token, new_token
from app.auth.sessions import now
from app.models.invite import Invite
from app.models.user import User

DEFAULT_INVITE_DAYS = 7


def create_invite(db: Session, days: int = DEFAULT_INVITE_DAYS) -> str:
    """Create an invite valid for `days`; returns the code (shown once, never stored)"""
    code = new_token(12)
    db.add(Invite(code_hash=hash_token(code), expires_at=now() + timedelta(days=days)))
    db.flush()
    return code


def redeem_invite(db: Session, code: str, user: User) -> Invite:
    """Mark an unused, unexpired invite as used by `user`; 422 `invalid_invite` otherwise.

    The row is locked so two sign-ups can't use the same invite.
    """
    invite = db.scalar(select(Invite).where(Invite.code_hash == hash_token(code)).with_for_update())
    if invite is None or invite.used_at is not None or invite.expires_at <= now():
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_invite",
            "This invite code isn't valid; it may be used or expired",
        )
    invite.used_at = now()
    invite.used_by = user
    return invite
