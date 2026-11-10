import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.auth.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.common import WeightUnit
from app.schemas.common import ReadModel, UpdateModel, omitted

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Password = Annotated[
    str, StringConstraints(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class RegistrationCreate(BaseModel):
    invite_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    email: Email
    password: Password
    display_name: DisplayName
    weight_unit: WeightUnit = WeightUnit.KG


# Any length is accepted when checking a password; a wrong one just fails to match
GivenPassword = Annotated[str, StringConstraints(max_length=MAX_PASSWORD_LENGTH)]


class SessionCreate(BaseModel):
    email: Email
    password: GivenPassword


class UserRead(ReadModel):
    id: uuid.UUID
    email: str
    display_name: str
    weight_unit: WeightUnit


class SessionRead(BaseModel):
    """The logged-in user, plus the CSRF token to send as X-CSRF-Token on unsafe requests"""

    user: UserRead
    csrf_token: str


class ProfileUpdate(UpdateModel):
    display_name: DisplayName = omitted()
    weight_unit: WeightUnit = omitted()


class PasswordUpdate(BaseModel):
    current_password: GivenPassword
    # The same rules as sign-up
    new_password: Password


class UserSessionRead(BaseModel):
    """One of the user's logins. `last_seen_at` is accurate to the hour"""

    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    # True for the session making this request
    current: bool
