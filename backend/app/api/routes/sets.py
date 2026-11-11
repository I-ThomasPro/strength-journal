import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_set, get_workout_exercise, reorder
from app.api.visibility import require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.common import WeightUnit
from app.models.ordering import place, remove
from app.models.set import Set
from app.models.workout import WorkoutExercise
from app.schemas.common import NewForm, Page, enum_options
from app.schemas.set import SetCreate, SetDefaults, SetOrder, SetRead, SetUpdate

# The sets of an exercise in a workout, in order. Only the user's own routines can be changed
router = APIRouter(tags=["sets"])


def own_workout_exercise(
    db: DbSession, workout_exercise_id: uuid.UUID, user_id: uuid.UUID
) -> WorkoutExercise:
    workout_exercise = get_workout_exercise(db, workout_exercise_id, user_id)
    require_owned(workout_exercise.workout.routine, user_id)
    return workout_exercise


@router.get("/workout-exercises/{workout_exercise_id}/sets")
def index(
    workout_exercise_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[SetRead]:
    """The sets in position order"""
    workout_exercise = get_workout_exercise(db, workout_exercise_id, user.id)
    statement = (
        select(Set).where(Set.workout_exercise_id == workout_exercise.id).order_by(Set.position)
    )
    sets, total = paginate(db, statement, page)
    return Page(items=[SetRead.model_validate(set_) for set_ in sets], total=total)


@router.get("/workout-exercises/{workout_exercise_id}/sets/new")
def new(workout_exercise_id: uuid.UUID, user: CurrentUser, db: DbSession) -> NewForm[SetDefaults]:
    """Suggested values for the next set: a copy of the last set's targets, or just the user's
    preferred unit for the first set"""
    workout_exercise = own_workout_exercise(db, workout_exercise_id, user.id)
    last = workout_exercise.sets[-1] if workout_exercise.sets else None
    defaults = SetDefaults(
        target_reps=last.target_reps if last else None,
        target_weight=last.target_weight if last else None,
        weight_unit=last.weight_unit if last else user.weight_unit,
    )
    return NewForm(defaults=defaults, options=enum_options(weight_unit=WeightUnit))


@router.post("/workout-exercises/{workout_exercise_id}/sets", status_code=status.HTTP_201_CREATED)
def create(
    workout_exercise_id: uuid.UUID, body: SetCreate, user: CurrentUser, db: DbSession
) -> SetRead:
    """Add a set at the end, or at `position`, shifting later ones"""
    workout_exercise = own_workout_exercise(db, workout_exercise_id, user.id)
    set_ = Set(
        target_reps=body.target_reps,
        target_weight=body.target_weight,
        weight_unit=body.weight_unit or user.weight_unit,
        position=0,
    )
    workout_exercise.sets = place(workout_exercise.sets, set_, body.position)
    db.flush()
    return SetRead.model_validate(set_)


@router.put("/workout-exercises/{workout_exercise_id}/sets/order")
def order(
    workout_exercise_id: uuid.UUID, body: SetOrder, user: CurrentUser, db: DbSession
) -> list[SetRead]:
    """Set the order of all the sets at once; returns them in the new order"""
    workout_exercise = own_workout_exercise(db, workout_exercise_id, user.id)
    workout_exercise.sets = reorder(workout_exercise.sets, body.set_ids, "exercise's sets")
    db.flush()
    return [SetRead.model_validate(set_) for set_ in workout_exercise.sets]


@router.get("/sets/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> SetRead:
    return SetRead.model_validate(get_set(db, id, user.id))


@router.patch("/sets/{id}")
def update(id: uuid.UUID, body: SetUpdate, user: CurrentUser, db: DbSession) -> SetRead:
    """Change the targets or unit, or move the set with `position`"""
    set_ = get_set(db, id, user.id)
    workout_exercise = set_.workout_exercise
    require_owned(workout_exercise.workout.routine, user.id)
    body.apply_to(set_, exclude={"position"})
    if "position" in body.model_fields_set:
        workout_exercise.sets = place(workout_exercise.sets, set_, body.position)
    db.flush()
    return SetRead.model_validate(set_)


@router.delete("/sets/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete the set; later sets move up"""
    set_ = get_set(db, id, user.id)
    workout_exercise = set_.workout_exercise
    require_owned(workout_exercise.workout.routine, user.id)
    workout_exercise.sets = remove(workout_exercise.sets, set_)
    db.delete(set_)
