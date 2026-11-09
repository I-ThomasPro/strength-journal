"""Simple model factories: build a valid record, override any field, add it and flush"""

import uuid

from sqlalchemy.orm import Session

from app.models.user import User


def create_user(session: Session, **overrides: object) -> User:
    unique = uuid.uuid4().hex[:12]
    fields: dict[str, object] = {
        "email": f"user-{unique}@example.com",
        "password_hash": "not-a-real-hash",
        "display_name": f"User {unique}",
    }
    user = User(**(fields | overrides))
    session.add(user)
    session.flush()
    return user
