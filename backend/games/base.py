"""Shared contract for puzzle-game plugins.

The HTTP layer (:mod:`routes.games`) owns authentication, JSON parsing,
guest-hint bookkeeping and status-code policy.  A game plugin owns only its
content, rule validation and scoring so that adding a game does not require
editing the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

User = dict[str, Any] | None
Params = Any
StatusPolicy = Literal["always_200", "422_if_incorrect"]


@dataclass(frozen=True)
class OverviewContext:
    """Read-only snapshot handed to a game's overview formatter.

    ``stats`` is the per-game row returned by ``storage.get_game_run_stats``;
    ``daily_completed`` is already resolved for ``date``.
    """

    user: User
    date: str
    stats: dict[str, Any]
    daily_completed: bool


@dataclass(frozen=True)
class GameSpec:
    """Everything the generic router needs to serve one game.

    ``start`` receives the raw query parameters (a Flask ``MultiDict``) so a
    game can keep its own parameter names without the router knowing them.
    ``save``/``hint``/``submit`` receive the decoded JSON body; ``hint`` and
    ``submit`` also receive the number of hints already consumed by a guest.
    """

    key: str
    title: str
    daily: bool = False
    levels: int = 0
    guest: bool = True
    order: int = 100
    start: Callable[[User, Params], dict[str, Any]] | None = None
    catalog: Callable[[User], dict[str, Any]] | None = None
    save: Callable[[User, dict[str, Any]], dict[str, Any]] | None = None
    hint: Callable[[User, dict[str, Any], int], dict[str, Any]] | None = None
    submit: Callable[[User, dict[str, Any], int], dict[str, Any]] | None = None
    overview: Callable[[OverviewContext], tuple[str, float]] | None = None
    status: StatusPolicy = "422_if_incorrect"

    def supports(self, action: str) -> bool:
        return getattr(self, action, None) is not None
