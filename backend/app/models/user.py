from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db import Base
from app.models.common import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    WeightUnit,
    WeightUnitType,
    weight_unit_check,
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (weight_unit_check("weight_unit"),)

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    weight_unit: Mapped[WeightUnit] = mapped_column(
        WeightUnitType(),
        nullable=False,
        default=WeightUnit.KG,
        server_default=WeightUnit.KG.value,
    )

    @validates("email")
    def _lowercase_email(self, _key: str, email: str) -> str:
        return email.lower()
