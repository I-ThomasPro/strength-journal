"""Admin commands:

- `python -m app.cli create-admin [--username U] [--display-name N] [--weight-unit kg|lb]
  [--password-stdin]` creates an admin account, asking for anything not given. The password
  is asked for twice, or read from the first line of stdin with --password-stdin
- `python -m app.cli create-invite [--days 7]` creates a sign-up code (no screen uses them)
"""

import argparse
import sys
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.accounts import add_account
from app.auth.invites import DEFAULT_INVITE_DAYS, create_invite
from app.db import SessionLocal
from app.models.common import WeightUnit
from app.models.user import User
from app.schemas.auth import UserCreate

SessionFactory = Callable[[], AbstractContextManager[Session]]


def main(argv: Sequence[str] | None = None, session_factory: SessionFactory = SessionLocal) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    admin = commands.add_parser(
        "create-admin", help="create an admin account, asking for anything not given"
    )
    admin.add_argument("--username")
    admin.add_argument("--display-name")
    admin.add_argument("--weight-unit", choices=[unit.value for unit in WeightUnit])
    admin.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from the first line of stdin (needs --username and --display-name)",
    )

    invite = commands.add_parser("create-invite", help="create a single-use sign-up code")
    invite.add_argument(
        "--days",
        type=int,
        default=DEFAULT_INVITE_DAYS,
        help=f"days until the code expires (default {DEFAULT_INVITE_DAYS})",
    )
    args = parser.parse_args(argv)

    if args.command == "create-admin":
        if args.password_stdin and (args.username is None or args.display_name is None):
            parser.error("--password-stdin needs --username and --display-name")
        return create_admin(args, session_factory)

    if args.days < 1:
        parser.error("--days must be at least 1")
    with session_factory() as db:
        code = create_invite(db, days=args.days)
        db.commit()
    days = "1 day" if args.days == 1 else f"{args.days} days"
    print(f"Invite code (valid for {days}; it won't be shown again): {code}")
    return 0


def create_admin(args: argparse.Namespace, session_factory: SessionFactory) -> int:
    username = args.username if args.username is not None else input("Username: ")
    display_name = args.display_name if args.display_name is not None else input("Display name: ")
    weight_unit = args.weight_unit
    if weight_unit is None and not args.password_stdin:
        weight_unit = input("Weight unit (kg or lb) [kg]: ").strip()
    # With --password-stdin nothing is asked for, since stdin holds the password
    weight_unit = weight_unit or WeightUnit.KG.value
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass("Password: ")
        if getpass("Password again: ") != password:
            return fail("The passwords don't match")

    try:
        account = UserCreate(
            username=username,
            display_name=display_name,
            password=password,
            weight_unit=weight_unit,
            is_admin=True,
        )
    except ValidationError as error:
        return fail(
            *(
                f"{'.'.join(map(str, e['loc']))}: {e['msg']}"
                for e in error.errors(include_input=False)
            )
        )

    with session_factory() as db:
        if db.scalar(select(User.id).where(User.username == account.username)) is not None:
            return fail(f"The username {account.username!r} is taken")
        add_account(db, account)
        db.commit()
    print(f"Created the admin {account.username!r}; log in with that username and password")
    return 0


def fail(*messages: str) -> int:
    for message in messages:
        print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
