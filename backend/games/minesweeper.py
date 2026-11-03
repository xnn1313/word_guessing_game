"""Daily minesweeper plugin adapter."""

from __future__ import annotations

import minesweeper

from . import register
from .base import GameSpec


def _start(user, params):
    return minesweeper.start(user, params)


def _save(user, data):
    return minesweeper.save(user, data)


def _submit(user, data, guest_hints):
    return minesweeper.submit(user, data)


def _overview(ctx):
    if not ctx.user:
        return "登录后同步进度", 0.0
    if ctx.daily_completed:
        return "今日雷区已扫清", 100.0
    best = ctx.stats.get("minesweeper", {}).get("best_score")
    return (f"最佳 {best} 分" if best is not None else "9×9 · 10 颗雷"), 0.0


register(
    GameSpec(
        key="minesweeper",
        title="每日扫雷",
        daily=True,
        order=90,
        overview=_overview,
        start=_start,
        save=_save,
        submit=_submit,
    )
)
