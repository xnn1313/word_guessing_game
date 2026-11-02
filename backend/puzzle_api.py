"""Backward-compatible entry point for the puzzle HTTP surface.

The implementation lives in :mod:`routes.games`; ``app.py`` and the existing
tests still call ``register_puzzle_routes`` so the old name stays available
while the rest of the application migrates.
"""

from __future__ import annotations

from routes.games import MAX_JSON_BYTES, register_game_routes

register_puzzle_routes = register_game_routes

__all__ = ["MAX_JSON_BYTES", "register_puzzle_routes"]
