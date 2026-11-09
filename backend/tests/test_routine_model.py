from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from tests.factories import create_routine, create_user


def test_library_routine_has_no_owner_and_optional_description(db_session: Session) -> None:
    routine = create_routine(db_session, name="Beginner 5x5")
    db_session.refresh(routine)

    assert routine.owner_id is None
    assert routine.owner is None
    assert routine.description is None
    assert routine.source_routine_id is None


def test_user_routine_belongs_to_its_owner(db_session: Session) -> None:
    user = create_user(db_session)
    routine = create_routine(
        db_session, name="My Split", description="Upper / lower, 4 days", owner=user
    )
    db_session.refresh(routine)

    assert routine.owner_id == user.id
    assert routine.owner is user
    assert routine.description == "Upper / lower, 4 days"


def test_copy_links_to_its_source(db_session: Session) -> None:
    user = create_user(db_session)
    source = create_routine(db_session, name="Push / Pull / Legs")
    copy = create_routine(db_session, name="Push / Pull / Legs", owner=user, source_routine=source)
    db_session.refresh(copy)

    assert copy.source_routine_id == source.id
    assert copy.source_routine is source


def test_deleting_the_source_keeps_the_copy_and_clears_the_link(db_session: Session) -> None:
    user = create_user(db_session)
    source = create_routine(db_session)
    copy = create_routine(db_session, owner=user, source_routine=source)
    copy_id = copy.id

    db_session.delete(source)
    db_session.flush()
    db_session.expunge_all()

    remaining = db_session.get(Routine, copy_id)
    assert remaining is not None
    assert remaining.source_routine_id is None


def test_deleting_a_user_deletes_their_routines_but_not_the_library(db_session: Session) -> None:
    user = create_user(db_session)
    library = create_routine(db_session)
    own = create_routine(db_session, owner=user)
    library_id, own_id = library.id, own.id

    db_session.delete(user)
    db_session.flush()
    db_session.expunge_all()

    remaining = set(db_session.scalars(select(Routine.id)))
    assert library_id in remaining
    assert own_id not in remaining
