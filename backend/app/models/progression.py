from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import (
    TextEnum,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WeightUnit,
    WeightUnitType,
    enum_check,
    weight_unit_check,
)
from app.models.exercise import Exercise
from app.models.routine import Routine


class ProgressionCondition(StrEnum):
    # Every Set of the exercise completed at its target reps; the only condition in v1
    ALL_SETS_COMPLETED = "all_sets_completed"


class Progression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How an Exercise in a Routine is progressively overloaded on later completions.

    Keyed by routine + exercise, so one Progression applies wherever that Exercise appears in
    the Routine's Workouts. Exercises without one keep their weight until the user changes it.
    Applying a progression after a workout is not part of the schema.
    """

    __tablename__ = "progressions"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    # An exercise with a progression can't be deleted. Deferred to commit for the same reason
    # as workout_exercises.exercise_id: deleting a user cascades to their routines too
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    # Weight added each time the condition is met
    increment: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    increment_unit: Mapped[WeightUnit] = mapped_column(WeightUnitType(), nullable=False)
    condition: Mapped[ProgressionCondition] = mapped_column(
        TextEnum(ProgressionCondition),
        nullable=False,
        default=ProgressionCondition.ALL_SETS_COMPLETED,
        server_default=ProgressionCondition.ALL_SETS_COMPLETED.value,
    )

    # Many-to-one only: Routine.progressions / Exercise.progressions collections without
    # passive_deletes would make the ORM rewrite rows the database already handles
    routine: Mapped[Routine] = relationship()
    exercise: Mapped[Exercise] = relationship()

    __table_args__ = (
        # One progression per exercise in a routine; also serves lookups by routine_id
        UniqueConstraint(
            "routine_id", "exercise_id", name="uq_progressions_routine_id_exercise_id"
        ),
        CheckConstraint("increment > 0", name="increment_positive"),
        weight_unit_check("increment_unit"),
        enum_check("condition", ProgressionCondition),
    )
