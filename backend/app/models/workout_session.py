from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.routine_cycle import RoutineCycle
from app.models.routine_workout import RoutineWorkout
from app.models.user import User

if TYPE_CHECKING:
    from app.models.workout import Workout


class WorkoutSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One time a user performed a workout: from a slot in a routine's cycle, or freestyle.

    The id may come from the client, so a session can be created offline. Deleting the slot,
    workout or routine keeps the session as history (their references become null).
    """

    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Null for a freestyle session, or once the slot is removed from the cycle
    routine_workout_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routine_workouts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Kept when the slot is removed, so the session still says which workout it was
    workout_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workouts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routine_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # When the workout was done. Editable, so a session entered later can be back-dated
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    # Many-to-one only: collections on the other side without passive_deletes would make the
    # ORM rewrite rows the database already handles
    user: Mapped[User] = relationship()
    routine_workout: Mapped[RoutineWorkout | None] = relationship()
    workout: Mapped[Workout | None] = relationship()
    cycle: Mapped[RoutineCycle | None] = relationship()

    __table_args__ = (
        # A user's sessions, newest first; its leading user_id also serves the user cascade
        Index("ix_workout_sessions_user_id_performed_at", "user_id", "performed_at"),
    )
