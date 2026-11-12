"""Creating accounts, shared by `POST /api/users` and `python -m app.cli create-admin`"""

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models.user import User
from app.schemas.auth import UserCreate


def add_account(db: Session, account: UserCreate) -> User:
    """Add the account, storing only its password's hash. A taken username fails the flush
    (`uq_users_username`)"""
    user = User(
        username=account.username,
        password_hash=hash_password(account.password),
        display_name=account.display_name,
        weight_unit=account.weight_unit,
        is_admin=account.is_admin,
    )
    db.add(user)
    db.flush()
    return user
