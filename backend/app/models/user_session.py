import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import UUIDPrimaryKeyMixin
from app.models.user import User


class UserSession(UUIDPrimaryKeyMixin, Base):
    """A login on one device. The cookie holds a random token; only its hash is stored here,
    so a database leak doesn't expose live sessions"""

    __tablename__ = "user_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SHA-256 of the cookie token
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Must be sent back in the X-CSRF-Token header on unsafe requests
    csrf_token: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Many-to-one only, like the other models: deleting a user is left to the database
    user: Mapped[User] = relationship()
