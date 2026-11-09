import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.auth.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.models.common import WeightUnit
from app.schemas.common import ReadModel

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


class SessionCreate(BaseModel):
    email: Email
    # Any length is accepted here; a wrong password just fails to match
    password: Annotated[str, StringConstraints(max_length=MAX_PASSWORD_LENGTH)]


class UserRead(ReadModel):
    id: uuid.UUID
    email: str
    display_name: str
    weight_unit: WeightUnit


class SessionRead(BaseModel):
    """The logged-in user, plus the CSRF token to send as X-CSRF-Token on unsafe requests"""

    user: UserRead
    csrf_token: str
