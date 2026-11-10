import uuid
from datetime import datetime

from app.schemas.common import ReadModel
from app.schemas.exercise import ExerciseSummary
from app.schemas.set import SetRead


class WorkoutRead(ReadModel):
    id: uuid.UUID
    routine_id: uuid.UUID
    name: str
    position: int
    created_at: datetime
    updated_at: datetime


class WorkoutExerciseRead(ReadModel):
    """An exercise at a position in a workout"""

    id: uuid.UUID
    workout_id: uuid.UUID
    position: int
    exercise: ExerciseSummary
    created_at: datetime
    updated_at: datetime


class WorkoutExerciseDetail(WorkoutExerciseRead):
    sets: list[SetRead]


class WorkoutDetail(WorkoutRead):
    exercises: list[WorkoutExerciseDetail]
