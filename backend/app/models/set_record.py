from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    func,
)
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
from app.models.user import User


class SetRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The reps a user actually completed, and at what weight, for an Exercise.

    Independent of Sets: Sets are what a Routine prescribes, SetRecords are what was lifted.
    Editing or deleting Routines, Workouts or Sets never changes recorded history.
    """

    __tablename__ = "set_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # An exercise that has records can't be deleted. Deferred to commit because deleting a
    # user removes both their records and their custom exercises (see workout_exercises)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    # 0 is allowed so a failed attempt can be recorded
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    # As the user entered it
    weight_unit: Mapped[WeightUnit] = mapped_column(WeightUnitType(), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Many-to-one only: User.set_records / Exercise.set_records collections without
    # passive_deletes would make the ORM rewrite rows the database already handles
    user: Mapped[User] = relationship()
    exercise: Mapped[Exercise] = relationship()

    __table_args__ = (
        # A user's history of an exercise; its leading user_id also serves the user cascade
        Index(
            "ix_set_records_user_id_exercise_id_performed_at",
            "user_id",
            "exercise_id",
            "performed_at",
        ),
        CheckConstraint("reps >= 0", name="reps_non_negative"),
        CheckConstraint("weight >= 0", name="weight_non_negative"),
        weight_unit_check("weight_unit"),
    )
