"""Pagination, visibility and form-data helpers shared by the resource endpoints"""

import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.pagination import PageParams, PageQuery, paginate
from app.api.visibility import get_visible_or_404, require_owned, visible_to
from app.db import DbSession
from app.main import create_app
from app.models.common import WeightUnit
from app.models.exercise import Exercise, ExerciseType
from app.schemas.common import EditForm, NewForm, Page, ReadModel, enum_options
from tests.factories import create_exercise, create_user
from tests.helpers import assert_error


class ExerciseRead(ReadModel):
    name: str


def test_paginate_returns_one_page_and_the_total(db_session: Session) -> None:
    for name in ["A", "B", "C", "D", "E"]:
        create_exercise(db_session, name=f"Paged {name}")
    statement = select(Exercise).where(Exercise.name.like("Paged %")).order_by(Exercise.name)

    items, total = paginate(db_session, statement, PageParams(limit=2, offset=2))

    assert [item.name for item in items] == ["Paged C", "Paged D"]
    assert total == 5


@pytest.fixture
def paging_client(client_for: Callable[[FastAPI], TestClient]) -> TestClient:
    app = create_app()
    router = APIRouter(prefix="/api/test-exercises", tags=["test"])

    @router.get("")
    def index(db: DbSession, page: PageQuery) -> Page[ExerciseRead]:
        statement = select(Exercise).where(Exercise.name.like("Listed %")).order_by(Exercise.name)
        items, total = paginate(db, statement, page)
        return Page[ExerciseRead](items=items, total=total)

    app.include_router(router)
    return client_for(app)


def test_index_pages_default_and_limit(paging_client: TestClient, db_session: Session) -> None:
    for number in range(3):
        create_exercise(db_session, name=f"Listed {number}")

    everything = paging_client.get("/api/test-exercises").json()
    second = paging_client.get("/api/test-exercises?limit=1&offset=1").json()

    assert everything["total"] == 3 and len(everything["items"]) == 3
    assert second == {"items": [{"name": "Listed 1"}], "total": 3}


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "offset=-1"])
def test_index_rejects_out_of_range_paging(paging_client: TestClient, query: str) -> None:
    assert_error(paging_client.get(f"/api/test-exercises?{query}"), 422, "invalid")


def test_visible_to_is_the_library_plus_the_users_own(db_session: Session) -> None:
    me, other = create_user(db_session), create_user(db_session)
    library = create_exercise(db_session)
    mine = create_exercise(db_session, owner=me)
    theirs = create_exercise(db_session, owner=other)

    visible = set(db_session.scalars(select(Exercise.id).where(visible_to(Exercise, me.id))))

    assert {library.id, mine.id} <= visible
    assert theirs.id not in visible


def test_get_visible_or_404(db_session: Session) -> None:
    me, other = create_user(db_session), create_user(db_session)
    library = create_exercise(db_session)
    mine = create_exercise(db_session, owner=me)
    theirs = create_exercise(db_session, owner=other)

    assert get_visible_or_404(db_session, Exercise, library.id, me.id) is library
    assert get_visible_or_404(db_session, Exercise, mine.id, me.id) is mine
    for missing_id in [theirs.id, uuid.uuid4()]:
        with pytest.raises(ApiError) as error:
            get_visible_or_404(db_session, Exercise, missing_id, me.id)
        assert (error.value.status_code, error.value.code) == (404, "not_found")


def test_require_owned(db_session: Session) -> None:
    me, other = create_user(db_session), create_user(db_session)

    require_owned(create_exercise(db_session, owner=me), me.id)
    with pytest.raises(ApiError) as library_error:
        require_owned(create_exercise(db_session), me.id)
    with pytest.raises(ApiError) as other_error:
        require_owned(create_exercise(db_session, owner=other), me.id)

    assert (library_error.value.status_code, library_error.value.code) == (403, "read_only")
    assert (other_error.value.status_code, other_error.value.code) == (404, "not_found")


class SetFields(BaseModel):
    target_reps: int | None = None
    target_weight: Decimal | None = None
    weight_unit: WeightUnit | None = None


def test_new_and_edit_form_data() -> None:
    options = enum_options(weight_unit=WeightUnit, type=ExerciseType)
    new = NewForm[SetFields](defaults=SetFields(weight_unit=WeightUnit.KG), options=options)
    edit = EditForm[SetFields](
        values=SetFields(target_reps=5, target_weight=Decimal("100.00"), weight_unit=WeightUnit.LB),
        options=options,
    )

    assert new.model_dump(mode="json") == {
        "defaults": {"target_reps": None, "target_weight": None, "weight_unit": "kg"},
        "options": {"weight_unit": ["kg", "lb"], "type": ["strength"]},
    }
    assert edit.model_dump(mode="json")["values"] == {
        "target_reps": 5,
        "target_weight": "100.00",
        "weight_unit": "lb",
    }
