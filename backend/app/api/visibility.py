"""Who can see and change library and user-owned items (exercises, routines)

- Library items (no owner) are visible to everyone and read-only through the API
- Owned items are visible to, and changeable by, their owner only
- Another user's item is reported as missing (404), so ids don't reveal what exists
"""

import uuid
from typing import Any, Protocol

from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import Session

from app.api.errors import not_found, read_only


class Owned(Protocol):
    owner_id: Any


def visible_to(model: Any, user_id: uuid.UUID) -> ColumnElement[bool]:
    """Filter for `select(model)`: library items plus the user's own"""
    return or_(model.owner_id.is_(None), model.owner_id == user_id)


def get_visible_or_404[M: Owned](
    session: Session, model: type[M], item_id: uuid.UUID, user_id: uuid.UUID
) -> M:
    item = session.get(model, item_id)
    if item is None or (item.owner_id is not None and item.owner_id != user_id):
        raise not_found()
    return item


def require_owned(item: Owned, user_id: uuid.UUID) -> None:
    """Before `edit`, `update` or `destroy`: 403 for library items, 404 for other users'"""
    if item.owner_id is None:
        raise read_only()
    if item.owner_id != user_id:
        raise not_found()
