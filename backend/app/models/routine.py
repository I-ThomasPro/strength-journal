from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User

if TYPE_CHECKING:
    from app.models.workout import Workout


class Routine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A routine in the shared library (no owner) or a user's own routine.

    A Routine outlines a set of Workouts to be completed in a configured order.
    """

    __tablename__ = "routines"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # The library routine this one was copied from. Deleting the source keeps the copy
    source_routine_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routines.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # No User.routines or Routine.copies collections: without passive_deletes the ORM would
    # rewrite or delete rows the database already handles
    owner: Mapped[User | None] = relationship()
    source_routine: Mapped[Routine | None] = relationship(remote_side=lambda: [Routine.id])
    # passive_deletes leaves deleting a routine's workouts to the database's ON DELETE CASCADE
    workouts: Mapped[list[Workout]] = relationship(
        back_populates="routine",
        order_by="Workout.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_library(self) -> bool:
        """A shared library routine: visible to everyone, changed by no one through the API"""
        return self.owner_id is None
