import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from tests.factories import create_user


def test_defaults_are_set_on_insert(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.weight_unit is WeightUnit.KG


def test_timestamps_are_set_on_insert(db_session: Session) -> None:
    user = create_user(db_session)
    db_session.refresh(user)

    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None
    assert user.created_at == user.updated_at


def test_updated_at_changes_on_update(db_session: Session) -> None:
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)
    user = create_user(db_session, updated_at=long_ago)

    user.display_name = "Renamed"
    db_session.flush()
    db_session.refresh(user)

    assert user.updated_at > long_ago


def test_email_is_stored_lowercased(db_session: Session) -> None:
    user = create_user(db_session, email="Mixed.Case@Example.COM")

    stored = db_session.execute(
        text("SELECT email FROM users WHERE id = :id"), {"id": user.id}
    ).scalar_one()
    assert stored == "mixed.case@example.com"


@pytest.mark.parametrize("second_email", ["lifter@example.com", "LIFTER@example.com"])
def test_duplicate_email_is_rejected(db_session: Session, second_email: str) -> None:
    create_user(db_session, email="lifter@example.com")

    with pytest.raises(IntegrityError, match="uq_users_email"):
        create_user(db_session, email=second_email)


@pytest.mark.parametrize("unit", ["lb", WeightUnit.LB])
def test_valid_weight_unit_is_accepted(db_session: Session, unit: str) -> None:
    user = create_user(db_session, weight_unit=unit)
    db_session.refresh(user)

    assert user.weight_unit is WeightUnit.LB


@pytest.mark.parametrize("unit", ["stone", "KG", ""])
def test_invalid_weight_unit_is_rejected(db_session: Session, unit: str) -> None:
    with pytest.raises(IntegrityError, match="ck_users_weight_unit"):
        create_user(db_session, weight_unit=unit)
