import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import TextEnum, TimestampMixin, UUIDPrimaryKeyMixin, enum_check
from app.models.user import User


class ExerciseType(StrEnum):
    # Tracked by sets of reps at a given weight; the only type in v1
    STRENGTH = "strength"


class Exercise(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An exercise in the shared library (no owner) or a user's custom exercise"""

    __tablename__ = "exercises"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[ExerciseType] = mapped_column(
        TextEnum(ExerciseType),
        nullable=False,
        default=ExerciseType.STRENGTH,
        server_default=ExerciseType.STRENGTH.value,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    # Many-to-one only: a User.exercises collection without passive_deletes would make the ORM
    # null owner_id when a user is deleted, turning their exercises into library ones
    owner: Mapped[User | None] = relationship()

    __table_args__ = (
        enum_check("type", ExerciseType),
        # Names are unique, ignoring case, within the library (NULL owner) and within each user.
        # An index rather than a constraint because it uses an expression; it also serves
        # lookups by owner_id
        Index(
            "uq_exercises_owner_id_lower_name",
            owner_id,
            func.lower(name),
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    @property
    def is_library(self) -> bool:
        """A shared library exercise: visible to everyone, changed by no one through the API"""
        return self.owner_id is None
