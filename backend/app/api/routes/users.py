from fastapi import APIRouter, Depends, status

from app.auth.accounts import add_account
from app.auth.sessions import require_admin
from app.db import DbSession
from app.schemas.auth import UserCreate, UserRead

# Accounts, which only admins create (there's no self-service sign-up screen)
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: UserCreate, db: DbSession) -> UserRead:
    """Create an account that can log in straight away. Admins only: 403 `admin_only` for
    anyone else. A taken username is 409 `duplicate_username`"""
    return UserRead.model_validate(add_account(db, body))
