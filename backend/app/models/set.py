from __future__ import annotations

import uuid
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

if TYPE_CHECKING:
    from app.models.workout import WorkoutExercise


class Set(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One of a sequence of sets of an Exercise within a Workout: the reps and weight to lift"""

    __tablename__ = "sets"

    workout_exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_exercises.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    target_weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weight_unit: Mapped[WeightUnit] = mapped_column(WeightUnitType(), nullable=False)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")

    __table_args__ = (
        # Deferred to commit so a reorder can swap positions within one transaction.
        # Its leading workout_exercise_id column also serves lookups by workout exercise
        UniqueConstraint(
            "workout_exercise_id",
            "position",
            name="uq_sets_workout_exercise_id_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("target_reps > 0", name="target_reps_positive"),
        CheckConstraint("target_weight >= 0", name="target_weight_non_negative"),
        weight_unit_check("weight_unit"),
    )
