"""Positions for ordered children (a routine's workouts, a workout's exercises, their sets)

Positions are kept contiguous from 0. Every change renumbers the siblings in one go; the
deferred UNIQUE (parent_id, position) constraints allow the brief duplicates in between,
as long as it all happens in one transaction.

Each function takes the siblings in their current order (e.g. `routine.workouts`) and
returns the new order, with every `position` updated.
"""

from collections.abc import Sequence
from typing import Protocol


class Positioned(Protocol):
    position: int


def renumber[P: Positioned](items: Sequence[P]) -> list[P]:
    """Set positions 0, 1, 2, … in the given order"""
    ordered = list(items)
    for index, item in enumerate(ordered):
        if item.position != index:
            item.position = index
    return ordered


def place[P: Positioned](siblings: Sequence[P], item: P, position: int | None = None) -> list[P]:
    """Insert `item`, or move it if it's already a sibling, to `position`.

    No position (or one past the end) puts it last; a negative one puts it first.
    """
    others = [sibling for sibling in siblings if sibling is not item]
    index = len(others) if position is None else min(max(position, 0), len(others))
    others.insert(index, item)
    return renumber(others)


def remove[P: Positioned](siblings: Sequence[P], item: P) -> list[P]:
    """Take `item` out of the order and close the gap (deleting it is up to the caller)"""
    return renumber([sibling for sibling in siblings if sibling is not item])
