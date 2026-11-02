"""Memory matching plugin adapter."""

from __future__ import annotations

import puzzle_games

from . import register
from .base import GameSpec


def _start(user, params):
    return puzzle_games.get_memory(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("theme", "classic"),
        params.get("fresh") == "1",
    )


def _save(user, data):
    return puzzle_games.save_memory(user, data)


def _submit(user, data, guest_hints):
    return puzzle_games.submit_memory(user, data)


def _overview(ctx):
    if not ctx.user:
        return "尚无记录", 0.0
    best = ctx.stats.get("memory", {}).get("best_moves")
    return (f"最佳 {best} 步" if best is not None else "尚无记录"), 0.0


register(
    GameSpec(
        key="memory",
        title="记忆翻牌",
        daily=True,
        order=30,
        overview=_overview,
        start=_start,
        save=_save,
        submit=_submit,
    )
)
