"""Build the game hub overview from the plugin registry.

Only the word game lives outside the registry (it predates it), so its entry
is appended explicitly.  Every other tile and all summary counters derive from
``GameSpec`` metadata, which means adding a game does not touch this file.
"""

from __future__ import annotations

from typing import Any

import puzzle_games
import storage
from games import REGISTRY
from games.base import OverviewContext

WORD_KEY = "word"
WORD_TITLE = "猜词实验室"
WORD_MAX_STARS = 780


def _timestamp(value):
    return puzzle_games._timestamp(value)


def _word_entry(user):
    word = storage.get_word_overview(user["id"]) if user else {}
    stars = int(word.get("total_stars") or 0)
    if not user:
        text, percent = "登录后同步进度", 0.0
    else:
        text, percent = f"{stars} / {WORD_MAX_STARS} 星", stars / WORD_MAX_STARS * 100
    return {
        "key": WORD_KEY,
        "title": WORD_TITLE,
        "availability": "available",
        "progress_text": text,
        "progress_percent": round(percent, 2),
        "best_score": None,
        "daily_completed": False,
        "last_played_at": _timestamp(word.get("last_played_at")),
    }, stars, _timestamp(word.get("last_played_at"))


def _prepare_daily(date):
    """Materialize today's deterministic picks before flags are read."""
    puzzle_games._daily_sudoku_pick(
        "medium", 1, storage.list_sudoku_puzzle_ids("medium")
    )
    idiom_daily = [
        item["id"]
        for item in storage.list_idiom_puzzles(True)
        if item["difficulty"] == "medium"
    ]
    puzzle_games._daily_pick("idiom", "medium", idiom_daily)
    memory_key = "medium:classic"
    if not storage.get_daily_puzzle_id("memory", date, memory_key):
        storage.set_daily_puzzle_id(
            "memory", date, memory_key, f"memory-{date}-medium-classic"
        )
    # Imported lazily to avoid a module cycle: extra_puzzles reuses helper
    # functions from puzzle_games.
    import extra_puzzles

    extra_puzzles.ensure_daily_puzzles()


def _game_entry(spec, ctx):
    text, percent = spec.overview(ctx) if spec.overview else ("", 0.0)
    current = ctx.stats.get(spec.key, {})
    return {
        "key": spec.key,
        "title": spec.title,
        "availability": "available",
        "progress_text": text,
        "progress_percent": round(percent, 2),
        "best_score": current.get("best_score"),
        "daily_completed": ctx.daily_completed,
        "last_played_at": _timestamp(current.get("last_played_at")),
    }


def build_overview(user) -> dict[str, Any]:
    date = puzzle_games.server_date()
    if user:
        _prepare_daily(date)
        flags = storage.get_daily_completion_flags(user["id"], date)
        stats = storage.get_game_run_stats(user["id"])
    else:
        flags = set()
        stats = {}

    word_entry, word_stars, word_last = _word_entry(user)
    games = [word_entry]
    for spec in sorted(REGISTRY.values(), key=lambda item: (item.order, item.key)):
        ctx = OverviewContext(
            user=user,
            date=date,
            stats=stats,
            daily_completed=spec.key in flags,
        )
        games.append(_game_entry(spec, ctx))

    total_stars = word_stars + sum(int(item.get("total_stars") or 0) for item in stats.values())
    last_candidates = [(key, _timestamp(value.get("last_played_at"))) for key, value in stats.items()]
    if word_last:
        last_candidates.append((WORD_KEY, word_last))
    last_candidates = [(key, value) for key, value in last_candidates if value]
    last_game = max(last_candidates, key=lambda item: item[1])[0] if last_candidates else None

    daily_keys = {spec.key for spec in REGISTRY.values() if spec.daily}
    return {
        "server_date": date,
        "summary": {
            "available_games": 1 + len(REGISTRY),
            "daily_total": len(daily_keys),
            "completed_today": len(flags & daily_keys),
            "total_stars": total_stars,
            "last_game_key": last_game,
        },
        "games": games,
    }
