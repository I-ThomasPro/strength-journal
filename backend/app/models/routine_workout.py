from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.routine import Routine
    from app.models.workout import Workout


class RoutineWorkout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A slot in a Routine's cycle: which of its Workouts comes at this position.

    A workout can fill several slots, so a cycle can repeat it (e.g. A, B, A).
    """

    __tablename__ = "routine_workouts"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    workout_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    routine: Mapped[Routine] = relationship(back_populates="slots")
    # Joined on workout_id alone; the composite foreign key below makes sure the workout is
    # the slot's own routine's
    workout: Mapped[Workout] = relationship(
        primaryjoin="RoutineWorkout.workout_id == Workout.id",
        foreign_keys="RoutineWorkout.workout_id",
    )

    __table_args__ = (
        # A slot can only point at a workout in its own routine. Deleting the workout
        # deletes its slots
        ForeignKeyConstraint(
            ["routine_id", "workout_id"],
            ["workouts.routine_id", "workouts.id"],
            name="fk_routine_workouts_routine_id_workout_id_workouts",
            ondelete="CASCADE",
        ),
        # Deferred to commit so a reorder can swap positions within one transaction.
        # Its leading routine_id column also serves lookups by routine
        UniqueConstraint(
            "routine_id",
            "position",
            name="uq_routine_workouts_routine_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        # For the cascade when a workout is deleted
        Index("ix_routine_workouts_workout_id", "workout_id"),
    )
