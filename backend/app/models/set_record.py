from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WeightUnit,
    WeightUnitType,
    weight_unit_check,
)
from app.models.exercise import Exercise
from app.models.set import Set

if TYPE_CHECKING:
    from app.models.workout_session import WorkoutSession


class SetRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A set the user actually did, at a position in a WorkoutSession: the reps completed, and
    at what weight, of an Exercise.

    A session can hold any number of records, more or fewer than its workout prescribes. A
    record done against a prescribed Set links to it and keeps a copy of its targets, so
    editing or deleting Routines, Workouts or Sets never changes recorded history.
    """

    __tablename__ = "set_records"

    # The owner and the time come from the session
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False
    )
    # An exercise that has records can't be deleted. Deferred to commit because deleting a
    # user removes both their records and their custom exercises (see workout_exercises)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    # The prescribed set this was done against, if any
    set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sets.id", ondelete="SET NULL"), nullable=True, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # 0 is allowed so a failed attempt can be recorded
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    # As the user entered it
    weight_unit: Mapped[WeightUnit] = mapped_column(WeightUnitType(), nullable=False)
    # The set's targets when it was linked: all set, or all null for an unlinked record
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    target_unit: Mapped[WeightUnit | None] = mapped_column(WeightUnitType(), nullable=True)

    session: Mapped[WorkoutSession] = relationship(back_populates="set_records")
    # Many-to-one only: Exercise.set_records / Set.set_records collections without
    # passive_deletes would make the ORM rewrite rows the database already handles
    exercise: Mapped[Exercise] = relationship()
    set: Mapped[Set | None] = relationship()

    __table_args__ = (
        # Deferred to commit so a reorder can swap positions within one transaction.
        # Its leading session_id column also serves lookups by session and its cascade
        UniqueConstraint(
            "session_id",
            "position",
            name="uq_set_records_session_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("reps >= 0", name="reps_non_negative"),
        CheckConstraint("weight >= 0", name="weight_non_negative"),
        weight_unit_check("weight_unit"),
        CheckConstraint(
            "(target_reps IS NULL) = (target_weight IS NULL) "
            "AND (target_weight IS NULL) = (target_unit IS NULL)",
            name="targets_all_or_none",
        ),
        weight_unit_check("target_unit"),
    )

    @property
    def performed_at(self) -> datetime:
        """When the set was done: its session's time"""
        return self.session.performed_at
