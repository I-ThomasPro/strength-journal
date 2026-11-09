import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import UUIDPrimaryKeyMixin
from app.models.user import User


class Invite(UUIDPrimaryKeyMixin, Base):
    """A single-use code that lets someone sign up. Only the code's hash is stored"""

    __tablename__ = "invites"

    # SHA-256 of the invite code
    code_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Kept when the user is deleted (SET NULL) so the invite still reads as used
    used_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    used_by: Mapped[User | None] = relationship()
