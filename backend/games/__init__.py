"""Puzzle-game plugin registry.

A game module calls :func:`register` at import time; :mod:`routes.games` and
the overview builder then work purely from :data:`REGISTRY`.  Adding a game
means adding one module here, not editing the router or the overview.
"""

from __future__ import annotations

from .base import GameSpec, User

REGISTRY: dict[str, GameSpec] = {}


def register(spec: GameSpec) -> GameSpec:
    if spec.key in REGISTRY:
        raise ValueError(f"duplicate game key: {spec.key}")
    REGISTRY[spec.key] = spec
    return spec


def get(key: str) -> GameSpec | None:
    return REGISTRY.get(key)


# Importing a module is what registers it.  Keep this list alphabetical so
# diffs stay small when games are added or removed.
from . import (  # noqa: E402,F401
    arrow_maze,
    idiom,
    memory,
    minesweeper,
    poetry,
    sokoban,
    sudoku,
    tile2048,
    word_search,
)
