from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Explicit constraint names keep Alembic migrations stable and reviewable
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def request_transaction(session: Session) -> Iterator[Session]:
    """One transaction per request: commit when the endpoint returns, roll back if it raises.

    Deferred constraints (positions, exercise references) are checked explicitly before the
    commit, so a violation surfaces inside the request as an IntegrityError the error handlers
    turn into a response, the same way in tests (which never really commit) as in production.
    """
    try:
        yield session
        session.flush()
        session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        session.commit()
    except BaseException:
        session.rollback()
        raise


def get_db() -> Iterator[Session]:
    """A database session for one request, inside its own transaction"""
    with SessionLocal() as session, request_transaction(session):
        yield session


def get_plain_session() -> Iterator[Session]:
    """A session without the request transaction, for the health check: it must answer
    even when the database is down, so it can't end the request with a commit"""
    with SessionLocal() as session:
        yield session


# scope="function" ends the transaction when the endpoint returns, before the response is
# sent, so a failed commit can still become an error response (the default "request" scope
# runs it after the response has started)
DbSession = Annotated[Session, Depends(get_db, scope="function")]
PlainSession = Annotated[Session, Depends(get_plain_session)]
