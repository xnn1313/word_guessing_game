"""Poetry quiz plugin adapter."""

from __future__ import annotations

import extra_puzzles

from . import register
from .base import GameSpec


def _start(user, params):
    return extra_puzzles.get_poetry(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("fresh") == "1",
    )


def _save(user, data):
    return extra_puzzles.save_poetry(user, data)


def _submit(user, data, guest_hints):
    # A wrong option is normal quiz feedback, not a transport error.
    return extra_puzzles.submit_poetry(user, data)


def _overview(ctx):
    if not ctx.user:
        return "五题热身", 0.0
    return ("今日已完成" if ctx.daily_completed else "五题热身"), (
        100.0 if ctx.daily_completed else 0.0
    )


register(
    GameSpec(
        key="poetry",
        title="诗词大会",
        daily=True,
        order=50,
        overview=_overview,
        start=_start,
        save=_save,
        submit=_submit,
        status="always_200",
    )
)
