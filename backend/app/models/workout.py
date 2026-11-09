from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.exercise import Exercise

if TYPE_CHECKING:
    from app.models.routine import Routine
    from app.models.set import Set


class Workout(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One workout in a Routine's configured order, outlining Exercises to complete in order"""

    __tablename__ = "workouts"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    routine: Mapped[Routine] = relationship(back_populates="workouts")
    # Each entry is a WorkoutExercise: an Exercise plus its position in this workout
    exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="workout",
        order_by=lambda: WorkoutExercise.position,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Deferred to commit so a reorder can swap positions within one transaction.
        # Its leading routine_id column also serves lookups by routine
        UniqueConstraint(
            "routine_id",
            "position",
            name="uq_workouts_routine_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )


class WorkoutExercise(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An Exercise at a position within a Workout, with its sequence of Sets"""

    __tablename__ = "workout_exercises"

    workout_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False
    )
    # An exercise that's used in a workout can't be deleted. The check is deferred to commit:
    # deleting a user removes both their custom exercises and their routines, and an
    # immediate check (RESTRICT, or plain NO ACTION, which Postgres checks after each
    # cascaded delete) would reject the exercise before the routine's rows are gone
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    workout: Mapped[Workout] = relationship(back_populates="exercises")
    # Many-to-one only: an Exercise.workout_exercises collection would make the ORM try to
    # null exercise_id on delete instead of letting the foreign key stop it
    exercise: Mapped[Exercise] = relationship()
    # passive_deletes leaves deleting the sets to the database's ON DELETE CASCADE
    sets: Mapped[list[Set]] = relationship(
        back_populates="workout_exercise",
        order_by="Set.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Deferred for the same reason as workouts; also serves lookups by workout_id
        UniqueConstraint(
            "workout_id",
            "position",
            name="uq_workout_exercises_workout_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )
