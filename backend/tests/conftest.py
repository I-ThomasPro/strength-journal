import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.sessions import CSRF_HEADER, start_session
from app.config import get_settings
from app.db import get_db, get_plain_session, request_transaction
from app.main import app
from app.models.user import User
from tests.factories import create_user
from tests.helpers import TEST_PASSWORD

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/strength_journal_test",
)
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine for the test database, migrated to the latest revision once per run"""
    alembic_config = Config(str(ALEMBIC_INI))
    alembic_config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(alembic_config, "head")

    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test, even if the code under test commits"""
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client_for(db_session: Session) -> Iterator[Callable[[FastAPI], TestClient]]:
    """Make an API client for an app whose requests use the test session.

    Each request still gets the real request transaction, so commits, rollbacks and deferred
    constraint checks behave as in production; the test's outer transaction undoes it all.
    """
    apps: list[FastAPI] = []

    def request_db() -> Iterator[Session]:
        # Treat the test's setup as committed, so a failed request only rolls back its own
        # changes (each commit or rollback here ends a savepoint, not the test's transaction)
        db_session.commit()
        # Requests share the test's database transaction, and each one ends with
        # SET CONSTRAINTS ALL IMMEDIATE, so restore the deferred default first
        db_session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        with request_transaction(db_session):
            yield db_session

    def make(target: FastAPI) -> TestClient:
        target.dependency_overrides[get_db] = request_db
        target.dependency_overrides[get_plain_session] = lambda: db_session
        apps.append(target)
        # HTTPS, so the Secure session cookie is sent back as it would be in production
        return TestClient(target, base_url="https://testserver")

    try:
        yield make
    finally:
        for target in apps:
            target.dependency_overrides.clear()


@pytest.fixture
def client(client_for: Callable[[FastAPI], TestClient]) -> Iterator[TestClient]:
    """API client for the real app, whose requests use the test session"""
    with client_for(app) as test_client:
        yield test_client


@pytest.fixture
def current_user(db_session: Session) -> User:
    """The user `logged_in_client` is logged in as; their password is TEST_PASSWORD"""
    return create_user(db_session, password_hash=hash_password(TEST_PASSWORD))


@pytest.fixture
def logged_in_client(client: TestClient, db_session: Session, current_user: User) -> TestClient:
    """API client logged in as `current_user`, sending the CSRF header on every request"""
    session, token = start_session(db_session, current_user)
    client.cookies.set(get_settings().session_cookie_name, token)
    client.headers[CSRF_HEADER] = session.csrf_token
    return client
