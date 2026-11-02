"""Sokoban plugin adapter."""

from __future__ import annotations

import extra_puzzles
import storage

from . import register
from .base import GameSpec


def _start(user, params):
    return extra_puzzles.get_sokoban(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("fresh") == "1",
        params.get("level"),
    )


def _catalog(user):
    return extra_puzzles.get_level_catalog(user, "sokoban")


def _save(user, data):
    return extra_puzzles.save_sokoban(user, data)


def _submit(user, data, guest_hints):
    return extra_puzzles.submit_sokoban(user, data)


def _overview(ctx):
    if not ctx.user:
        return "仓库待整理", 0.0
    done = len(storage.get_level_progress(ctx.user["id"], "sokoban"))
    return f"{done} / {LEVELS} 关", done / LEVELS * 100


LEVELS = 60

register(
    GameSpec(
        key="sokoban",
        title="推箱子",
        daily=True,
        levels=LEVELS,
        order=60,
        overview=_overview,
        catalog=_catalog,
        start=_start,
        save=_save,
        submit=_submit,
    )
)
