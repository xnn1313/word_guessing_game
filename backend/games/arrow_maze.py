"""Arrow-maze plugin adapter."""

from __future__ import annotations

import extra_puzzles
import storage

from . import register
from .base import GameSpec


def _start(user, params):
    return extra_puzzles.get_arrow_maze(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("fresh") == "1",
        params.get("level"),
    )


def _catalog(user):
    return extra_puzzles.get_level_catalog(user, "arrow_maze")


def _save(user, data):
    return extra_puzzles.save_arrow_maze(user, data)


def _hint(user, data, guest_hints):
    # The maze hint is positional; it does not depend on hint history.
    return extra_puzzles.hint_arrow_maze(user, data)


def _submit(user, data, guest_hints):
    return extra_puzzles.submit_arrow_maze(user, data)


def _overview(ctx):
    if not ctx.user:
        return "寻找出口", 0.0
    done = len(storage.get_level_progress(ctx.user["id"], "arrow_maze"))
    return f"{done} / {LEVELS} 关", done / LEVELS * 100


LEVELS = 60

register(
    GameSpec(
        key="arrow_maze",
        title="箭头迷宫",
        daily=True,
        levels=LEVELS,
        order=70,
        overview=_overview,
        catalog=_catalog,
        start=_start,
        save=_save,
        hint=_hint,
        submit=_submit,
    )
)
