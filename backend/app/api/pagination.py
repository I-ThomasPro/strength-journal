"""`limit` / `offset` paging for `index` actions"""

from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

MAX_LIMIT = 200


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


PageQuery = Annotated[PageParams, Depends(page_params)]


def paginate[T](
    session: Session, statement: Select[tuple[T]], params: PageParams
) -> tuple[list[T], int]:
    """Run an ordered `select` for one page; returns the page's items and the total count"""
    total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    items = list(session.scalars(statement.limit(params.limit).offset(params.offset)))
    return items, total or 0
