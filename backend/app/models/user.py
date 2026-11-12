from sqlalchemy import Text, false
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

    # Unique, and stored lowercased so logging in ignores case
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # Admins create accounts (POST /api/users); the first comes from `python -m app.cli
    # create-admin`
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    weight_unit: Mapped[WeightUnit] = mapped_column(
        WeightUnitType(),
        nullable=False,
        default=WeightUnit.KG,
        server_default=WeightUnit.KG.value,
    )

    @validates("username")
    def _lowercase_username(self, _key: str, username: str) -> str:
        return username.lower()
