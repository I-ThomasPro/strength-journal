import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.exercise import ExerciseType
from app.schemas.common import ReadModel, UpdateModel, omitted

ExerciseName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class ExerciseCreate(BaseModel):
    name: ExerciseName
    type: ExerciseType = ExerciseType.STRENGTH


class ExerciseUpdate(UpdateModel):
    name: ExerciseName = omitted()
    type: ExerciseType = omitted()


class ExerciseSummary(ReadModel):
    """An exercise as it appears inside a workout"""

    id: uuid.UUID
    name: str
    type: ExerciseType


class ExerciseRead(ReadModel):
    id: uuid.UUID
    name: str
    type: ExerciseType
    is_library: bool
    created_at: datetime
    updated_at: datetime
