"""Shared test helpers"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_deferred_constraints(session: Session) -> None:
    """Position uniqueness is checked at commit; force the check now (tests never commit)"""
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
