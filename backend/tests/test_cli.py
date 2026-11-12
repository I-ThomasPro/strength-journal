"""`python -m app.cli create-admin`, which creates the first admin"""

import io
from collections.abc import Callable, Iterator
from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cli
from app.models.common import WeightUnit
from app.models.user import User
from tests.factories import create_user

PASSWORD = "a long enough password"

Run = Callable[..., int]


@pytest.fixture
def run(db_session: Session) -> Run:
    """Runs the CLI against the test session"""

    def run_cli(*argv: str) -> int:
        return cli.main(list(argv), session_factory=lambda: nullcontext(db_session))

    return run_cli


def answer(monkeypatch: pytest.MonkeyPatch, *, inputs: list[str], passwords: list[str]) -> None:
    """Answers the prompts: `inputs` for input(), `passwords` for getpass()"""
    typed: Iterator[str] = iter(inputs)
    secret: Iterator[str] = iter(passwords)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(typed))
    monkeypatch.setattr(cli, "getpass", lambda _prompt="": next(secret))


def find(db_session: Session, username: str) -> User | None:
    db_session.expire_all()
    return db_session.scalar(select(User).where(User.username == username))


def test_creates_an_admin_from_answers_who_can_log_in(
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    client: TestClient,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answer(monkeypatch, inputs=["Coach", "Head Coach", "lb"], passwords=[PASSWORD, PASSWORD])

    assert run("create-admin") == 0

    admin = find(db_session, "coach")
    assert admin is not None
    assert (admin.is_admin, admin.display_name, admin.weight_unit) == (
        True,
        "Head Coach",
        WeightUnit.LB,
    )
    assert "Created the admin 'coach'" in capsys.readouterr().out
    login = client.post("/api/session", json={"username": "coach", "password": PASSWORD})
    assert login.status_code == 201, login.text
    assert login.json()["user"]["is_admin"] is True


def test_options_skip_their_questions_and_the_unit_defaults_to_kg(
    run: Run, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    answer(monkeypatch, inputs=[""], passwords=[PASSWORD, PASSWORD])

    assert run("create-admin", "--username", "coach", "--display-name", "Coach") == 0

    admin = find(db_session, "coach")
    assert admin is not None and admin.weight_unit == WeightUnit.KG


def test_reads_the_password_from_stdin_without_asking_anything(
    run: Run, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    answer(monkeypatch, inputs=[], passwords=[])
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{PASSWORD}\nignored\n"))

    exit_code = run(
        "create-admin", "--username", "coach", "--display-name", "Coach", "--password-stdin"
    )

    assert exit_code == 0
    admin = find(db_session, "coach")
    assert admin is not None and admin.is_admin and admin.weight_unit == WeightUnit.KG


def test_stdin_passwords_need_the_other_options(run: Run) -> None:
    with pytest.raises(SystemExit) as exit_info:
        run("create-admin", "--username", "coach", "--password-stdin")

    assert exit_info.value.code == 2


def test_passwords_that_dont_match_create_nothing(
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answer(monkeypatch, inputs=["coach", "Coach", ""], passwords=[PASSWORD, "something else"])

    assert run("create-admin") == 1

    assert "The passwords don't match" in capsys.readouterr().err
    assert find(db_session, "coach") is None


def test_a_taken_username_creates_nothing(
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    capsys: pytest.CaptureFixture[str],
) -> None:
    existing = create_user(db_session, username="coach")
    answer(monkeypatch, inputs=["Coach", "Coach", ""], passwords=[PASSWORD, PASSWORD])

    assert run("create-admin") == 1

    assert "The username 'coach' is taken" in capsys.readouterr().err
    assert find(db_session, "coach") == existing
    assert not existing.is_admin


def test_invalid_answers_are_explained(
    run: Run,
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answer(monkeypatch, inputs=["x", "Coach", "stone"], passwords=["short", "short"])

    assert run("create-admin") == 1

    errors = capsys.readouterr().err
    assert "username: String should have at least 3 characters" in errors
    assert "password: String should have at least 10 characters" in errors
    assert "weight_unit: Input should be 'kg' or 'lb'" in errors
    assert "short" not in errors
    assert find(db_session, "x") is None
