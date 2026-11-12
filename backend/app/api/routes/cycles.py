import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import current_cycle, open_cycle
from app.api.visibility import get_visible_or_404, require_owned
from app.auth.sessions import CurrentUser, now
from app.db import DbSession
from app.models.routine import Routine
from app.models.routine_cycle import RoutineCycle
from app.models.set import Set
from app.models.set_record import SetRecord
from app.models.workout import Workout, WorkoutExercise
from app.models.workout_session import WorkoutSession
from app.schemas.common import Page
from app.schemas.routine_cycle import NewCycleRead, RoutineCycleRead, SetTargetChange

# A routine's cycles: one pass each through its slots. Starting the next one carries what
# the user lifted into the plan; progression is otherwise manual
router = APIRouter(tags=["cycles"])


def latest_linked_records(
    db: Session, routine: Routine, cycle: RoutineCycle, user_id: uuid.UUID
) -> list[SetRecord]:
    """For each of the routine's sets, the latest record linked to it from the user's
    completed sessions in the cycle: by session performed_at, then the record's position"""
    return list(
        db.scalars(
            select(SetRecord)
            .join(SetRecord.session)
            .join(SetRecord.set)
            .join(Set.workout_exercise)
            .join(WorkoutExercise.workout)
            .where(
                Workout.routine_id == routine.id,
                WorkoutSession.cycle_id == cycle.id,
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed.is_(True),
            )
            # DISTINCT ON keeps the first row per set: the latest, by this ordering
            .ext(distinct_on(SetRecord.set_id))
            .order_by(
                SetRecord.set_id,
                WorkoutSession.performed_at.desc(),
                WorkoutSession.created_at.desc(),
                SetRecord.position.desc(),
            )
        )
    )


@router.get("/routines/{routine_id}/cycles")
def index(
    routine_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[RoutineCycleRead]:
    """The routine's cycles, newest first"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    statement = (
        select(RoutineCycle)
        .where(RoutineCycle.routine_id == routine.id)
        .order_by(RoutineCycle.number.desc())
    )
    cycles, total = paginate(db, statement, page)
    return Page(items=[RoutineCycleRead.model_validate(cycle) for cycle in cycles], total=total)


@router.post("/routines/{routine_id}/cycles", status_code=status.HTTP_201_CREATED)
def create(routine_id: uuid.UUID, user: CurrentUser, db: DbSession) -> NewCycleRead:
    """Start the next cycle of one of the user's routines. Each prescribed set takes the
    weight and unit of the latest record linked to it from a completed session in the
    current cycle; planned reps stay, unlinked records are history only, and sets with no
    record keep their targets. Then the current cycle closes and the next one opens"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    require_owned(routine, user.id)
    changes: list[SetTargetChange] = []
    cycle = current_cycle(db, routine)
    if cycle is not None:
        for record in latest_linked_records(db, routine, cycle, user.id):
            set_ = record.set
            assert set_ is not None  # joined on set_id above
            if (set_.target_weight, set_.weight_unit) == (record.weight, record.weight_unit):
                continue
            changes.append(
                SetTargetChange(
                    set_id=set_.id,
                    workout_exercise_id=set_.workout_exercise_id,
                    from_weight=set_.target_weight,
                    from_unit=set_.weight_unit,
                    to_weight=record.weight,
                    to_unit=record.weight_unit,
                )
            )
            set_.target_weight = record.weight
            set_.weight_unit = record.weight_unit
        cycle.completed_at = now()
        # Close it before opening the next, so there's never more than one open
        db.flush()
    next_cycle = open_cycle(db, routine)
    db.refresh(next_cycle)
    return NewCycleRead(
        **RoutineCycleRead.model_validate(next_cycle).model_dump(), changed_sets=changes
    )
