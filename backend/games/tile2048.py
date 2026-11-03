"""2048 plugin adapter."""

from __future__ import annotations

import tile_2048

from . import register
from .base import GameSpec


def _start(user, params):
    return tile_2048.start(user, params)


def _save(user, data):
    return tile_2048.save(user, data)


def _submit(user, data, guest_hints):
    return tile_2048.submit(user, data)


def _overview(ctx):
    if not ctx.user:
        return "登录后同步进度", 0.0
    if ctx.daily_completed:
        return "今日已完成", 100.0
    best = ctx.stats.get("tile2048", {}).get("best_score")
    return (f"最高 {best} 分" if best is not None else "滑动合并到 2048"), 0.0


register(
    GameSpec(
        key="tile2048",
        title="2048",
        daily=True,
        order=80,
        overview=_overview,
        start=_start,
        save=_save,
        submit=_submit,
    )
)
