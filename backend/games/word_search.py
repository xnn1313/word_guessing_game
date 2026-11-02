"""Word-search plugin adapter."""

from __future__ import annotations

import word_search

from . import register
from .base import GameSpec


def _catalog(user):
    return word_search.themes_catalog()


def _start(user, params):
    return word_search.get_board(
        user,
        params.get("mode"),
        params.get("difficulty"),
        params.get("theme", "classic"),
        params.get("board_id"),
        params.get("fresh") == "1",
    )


def _save(user, data):
    return word_search.save_progress(user, data)


def _submit(user, data, guest_hints):
    return word_search.submit_paths(user, data)


def _overview(ctx):
    if not ctx.user:
        return "开始连线", 0.0
    return ("今日已完成" if ctx.daily_completed else "开始连线"), (
        100.0 if ctx.daily_completed else 0.0
    )


register(
    GameSpec(
        key="word_search",
        title="成语连线",
        daily=True,
        order=40,
        overview=_overview,
        catalog=_catalog,
        start=_start,
        save=_save,
        submit=_submit,
    )
)
