from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.routine import Routine


class RoutineCycle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One pass through a Routine's slots. A routine has one open cycle at a time; workout
    sessions done from its slots belong to it"""

    __tablename__ = "routine_cycles"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routines.id", ondelete="CASCADE"), nullable=False
    )
    # 1, 2, 3... per routine
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Null while the cycle is open
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    routine: Mapped[Routine] = relationship()

    __table_args__ = (
        # Also serves lookups by routine
        UniqueConstraint("routine_id", "number", name="uq_routine_cycles_routine_id_number"),
        CheckConstraint("number >= 1", name="number_positive"),
        # One open cycle per routine
        Index(
            "uq_routine_cycles_routine_id_open",
            "routine_id",
            unique=True,
            postgresql_where=completed_at.is_(None),
        ),
    )
