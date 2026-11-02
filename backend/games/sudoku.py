"""Sudoku plugin adapter."""

from __future__ import annotations

import puzzle_games

from . import register
from .base import GameSpec


def _start(user, params):
    return puzzle_games.get_sudoku(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("daily_slot", 1),
    )


def _save(user, data):
    return puzzle_games.save_sudoku(user, data)


def _hint(user, data, guest_hints):
    return puzzle_games.hint_sudoku(user, data, guest_hints)


def _submit(user, data, guest_hints):
    return puzzle_games.submit_sudoku(user, data, guest_hints)


def _overview(ctx):
    if not ctx.user:
        return "今日未完成", 0.0
    return ("今日已完成" if ctx.daily_completed else "今日未完成"), (
        100.0 if ctx.daily_completed else 0.0
    )


register(
    GameSpec(
        key="sudoku",
        title="每日数独",
        daily=True,
        order=10,
        overview=_overview,
        start=_start,
        save=_save,
        hint=_hint,
        submit=_submit,
    )
)
