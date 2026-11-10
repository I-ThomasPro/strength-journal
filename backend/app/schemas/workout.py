import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.common import Position, ReadModel, UpdateModel, omitted
from app.schemas.exercise import ExerciseSummary
from app.schemas.set import SetRead

WorkoutName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WorkoutCreate(BaseModel):
    name: WorkoutName
    # Without one, the workout is added at the end
    position: Position | None = None


class WorkoutUpdate(UpdateModel):
    name: WorkoutName = omitted()
    # Moves the workout; the others shift to make room
    position: Position = omitted()


class WorkoutOrder(BaseModel):
    """Every one of the routine's workouts, in their new order"""

    workout_ids: list[uuid.UUID]


class WorkoutExerciseCreate(BaseModel):
    # A library exercise or one of the user's own
    exercise_id: uuid.UUID
    # Without one, the exercise is added at the end
    position: Position | None = None


class WorkoutExerciseUpdate(UpdateModel):
    # Swaps in a different exercise, keeping the sets
    exercise_id: uuid.UUID = omitted()
    # Moves it; the others shift to make room
    position: Position = omitted()


class WorkoutExerciseOrder(BaseModel):
    """Every one of the workout's exercises, in their new order"""

    workout_exercise_ids: list[uuid.UUID]


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
