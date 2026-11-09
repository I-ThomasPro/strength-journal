"""Simple model factories: build a valid record, override any field, add it and flush"""

import uuid

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.routine import Routine
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


def create_exercise(session: Session, **overrides: object) -> Exercise:
    """A shared library exercise unless `owner` or `owner_id` is given"""
    fields: dict[str, object] = {"name": f"Exercise {uuid.uuid4().hex[:12]}"}
    exercise = Exercise(**(fields | overrides))
    session.add(exercise)
    session.flush()
    return exercise


def create_routine(session: Session, **overrides: object) -> Routine:
    """A shared library routine unless `owner` or `owner_id` is given"""
    fields: dict[str, object] = {"name": f"Routine {uuid.uuid4().hex[:12]}"}
    routine = Routine(**(fields | overrides))
    session.add(routine)
    session.flush()
    return routine
