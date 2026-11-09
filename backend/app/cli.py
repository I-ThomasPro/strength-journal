"""Admin commands: `python -m app.cli create-invite [--days 7]`"""

import argparse
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.auth.invites import DEFAULT_INVITE_DAYS, create_invite
from app.db import SessionLocal


def main(
    argv: Sequence[str] | None = None,
    session_factory: Callable[[], AbstractContextManager[Session]] = SessionLocal,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    invite = commands.add_parser("create-invite", help="create a single-use sign-up code")
    invite.add_argument(
        "--days",
        type=int,
        default=DEFAULT_INVITE_DAYS,
        help=f"days until the code expires (default {DEFAULT_INVITE_DAYS})",
    )
    args = parser.parse_args(argv)

    if args.command == "create-invite":
        if args.days < 1:
            parser.error("--days must be at least 1")
        with session_factory() as db:
            code = create_invite(db, days=args.days)
            db.commit()
        days = "1 day" if args.days == 1 else f"{args.days} days"
        print(f"Invite code (valid for {days}; it won't be shown again): {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
