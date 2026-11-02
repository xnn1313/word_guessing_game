"""Idiom crossword plugin adapter."""

from __future__ import annotations

import puzzle_games
import storage

from . import register
from .base import GameSpec


def _catalog(user):
    return puzzle_games.idiom_catalog(user)


def _start(user, params):
    return puzzle_games.get_idiom(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("level_id"),
    )


def _save(user, data):
    return puzzle_games.save_idiom(user, data)


def _hint(user, data, guest_hints):
    return puzzle_games.hint_idiom(user, data, guest_hints)


def _submit(user, data, guest_hints):
    return puzzle_games.submit_idiom(user, data, guest_hints)


def _overview(ctx):
    total = max(1, len(storage.list_idiom_puzzles()))
    if not ctx.user:
        return f"0 / {total} 关", 0.0
    done = len(storage.get_idiom_progress(ctx.user["id"]))
    return f"{done} / {total} 关", done / total * 100


register(
    GameSpec(
        key="idiom",
        title="成语填字",
        daily=True,
        order=20,
        overview=_overview,
        catalog=_catalog,
        start=_start,
        save=_save,
        hint=_hint,
        submit=_submit,
    )
)
