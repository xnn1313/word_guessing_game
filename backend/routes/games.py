"""Generic HTTP layer for registered puzzle games.

Every game exposes the same actions:

    GET  /api/games/<key>/start      start (or resume) a round
    GET  /api/games/<key>/catalog    level/theme catalog, when the game has one
    POST /api/games/<key>/save       persist in-progress state
    POST /api/games/<key>/hint       reveal a hint
    POST /api/games/<key>/submit     validate a completed round

The legacy per-game paths (``/api/sudoku/puzzle`` …) are registered as thin
aliases over the same dispatch function so existing clients keep working.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session as flask_session

import puzzle_games
from games import get as get_game

MAX_JSON_BYTES = 64 * 1024

_START_ACTIONS = ("start", "catalog")
_MUTATING_ACTIONS = ("save", "hint", "submit")

PUZZLE_PREFIXES = (
    "/api/games/",
    "/api/sudoku/",
    "/api/idiom/",
    "/api/memory/",
    "/api/word-search/",
    "/api/poetry/",
    "/api/sokoban/",
    "/api/arrow-maze/",
)

# (path, game key, action, methods) — kept in sync with the old puzzle_api.py.
LEGACY_ROUTES = (
    ("/api/sudoku/puzzle", "sudoku", "start", ("GET",)),
    ("/api/sudoku/save", "sudoku", "save", ("POST",)),
    ("/api/sudoku/hint", "sudoku", "hint", ("POST",)),
    ("/api/sudoku/submit", "sudoku", "submit", ("POST",)),
    ("/api/idiom/catalog", "idiom", "catalog", ("GET",)),
    ("/api/idiom/puzzle", "idiom", "start", ("GET",)),
    ("/api/idiom/save", "idiom", "save", ("POST",)),
    ("/api/idiom/hint", "idiom", "hint", ("POST",)),
    ("/api/idiom/submit", "idiom", "submit", ("POST",)),
    ("/api/memory/board", "memory", "start", ("GET",)),
    ("/api/memory/save", "memory", "save", ("POST",)),
    ("/api/memory/submit", "memory", "submit", ("POST",)),
    ("/api/word-search/themes", "word_search", "catalog", ("GET",)),
    ("/api/word-search/board", "word_search", "start", ("GET",)),
    ("/api/word-search/save", "word_search", "save", ("POST",)),
    ("/api/word-search/submit", "word_search", "submit", ("POST",)),
    ("/api/poetry/quiz", "poetry", "start", ("GET",)),
    ("/api/poetry/save", "poetry", "save", ("POST",)),
    ("/api/poetry/submit", "poetry", "submit", ("POST",)),
    ("/api/sokoban/board", "sokoban", "start", ("GET",)),
    ("/api/sokoban/catalog", "sokoban", "catalog", ("GET",)),
    ("/api/sokoban/save", "sokoban", "save", ("POST",)),
    ("/api/sokoban/submit", "sokoban", "submit", ("POST",)),
    ("/api/arrow-maze/board", "arrow_maze", "start", ("GET",)),
    ("/api/arrow-maze/catalog", "arrow_maze", "catalog", ("GET",)),
    ("/api/arrow-maze/save", "arrow_maze", "save", ("POST",)),
    ("/api/arrow-maze/hint", "arrow_maze", "hint", ("POST",)),
    ("/api/arrow-maze/submit", "arrow_maze", "submit", ("POST",)),
)


def register_game_routes(app, get_current_user):
    """Register the generic game API and legacy aliases on ``app``."""

    def resolved_user():
        user = get_current_user()
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer ") and not user:
            raise puzzle_games.PuzzleError(
                "登录状态已失效，请重新登录", "INVALID_TOKEN", 401
            )
        return user

    def body():
        if request.content_length and request.content_length > MAX_JSON_BYTES:
            raise puzzle_games.PuzzleError("请求内容过大", "REQUEST_TOO_LARGE", 400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise puzzle_games.PuzzleError("请求体必须是 JSON 对象", "INVALID_JSON", 400)
        return data

    def guest_hint_count(game_key, puzzle_id):
        if resolved_user():
            return 0
        hints = flask_session.get("puzzle_guest_hints", {})
        key = f"{puzzle_games.server_date()}:{game_key}:{puzzle_id}"
        return int(hints.get(key, 0))

    def save_guest_hint(game_key, puzzle_id, count):
        if resolved_user():
            return
        hints = dict(flask_session.get("puzzle_guest_hints", {}))
        if len(hints) > 100:
            hints = {}
        hints[f"{puzzle_games.server_date()}:{game_key}:{puzzle_id}"] = int(count)
        flask_session["puzzle_guest_hints"] = hints

    def puzzle_id_of(data):
        return str(data.get("puzzle_id", ""))

    def dispatch(game_key, action):
        spec = get_game(game_key)
        if spec is None:
            raise puzzle_games.PuzzleError("未找到该游戏", "NOT_FOUND", 404)
        handler = getattr(spec, action, None)
        if not spec.supports(action) or handler is None:
            raise puzzle_games.PuzzleError("该游戏不支持此操作", "NOT_FOUND", 404)

        if action in _START_ACTIONS:
            if request.method != "GET":
                raise puzzle_games.PuzzleError(
                    "请求方法不允许", "METHOD_NOT_ALLOWED", 405
                )
            if action == "catalog":
                return jsonify(handler(resolved_user()))
            return jsonify(handler(resolved_user(), request.args))

        if action in _MUTATING_ACTIONS:
            if request.method != "POST":
                raise puzzle_games.PuzzleError(
                    "请求方法不允许", "METHOD_NOT_ALLOWED", 405
                )
            data = body()
            user = resolved_user()
            puzzle_id = puzzle_id_of(data)
            if action == "save":
                return jsonify(handler(user, data))
            if action == "hint":
                result = handler(user, data, guest_hint_count(game_key, puzzle_id))
                if "hints_used" in result:
                    save_guest_hint(game_key, puzzle_id, result["hints_used"])
                return jsonify(result)
            result = handler(user, data, guest_hint_count(game_key, puzzle_id))
            if spec.status == "always_200":
                return jsonify(result)
            return jsonify(result), 200 if result.get("correct") else 422

        raise puzzle_games.PuzzleError("未找到该操作", "NOT_FOUND", 404)

    def legacy_view(game_key, action):
        def view():
            return dispatch(game_key, action)

        view.__name__ = f"legacy_{game_key}_{action}"
        return view

    def overview():
        return jsonify(puzzle_games.games_overview(resolved_user()))

    def handle_puzzle_error(error):
        return jsonify({"error": error.message, "code": error.code}), error.status_code

    def handle_internal_error(error):
        if request.path.startswith(PUZZLE_PREFIXES):
            app.logger.error("益智游戏接口发生未处理错误: %s", error)
            return jsonify({"error": "服务器暂时无法处理请求", "code": "INTERNAL_ERROR"}), 500
        return error

    blueprint = Blueprint("games_api", __name__)
    blueprint.add_url_rule("/api/games/overview", "games_overview", overview, methods=["GET"])
    blueprint.add_url_rule(
        "/api/games/<game_key>/<action>",
        "game_action",
        lambda game_key, action: dispatch(game_key, action),
        methods=["GET", "POST"],
    )
    for path, game_key, action, methods in LEGACY_ROUTES:
        endpoint = "legacy_" + path.strip("/").replace("/", "_").replace("-", "_")
        blueprint.add_url_rule(path, endpoint, legacy_view(game_key, action), methods=methods)

    app.register_blueprint(blueprint)
    app.register_error_handler(puzzle_games.PuzzleError, handle_puzzle_error)
    app.register_error_handler(500, handle_internal_error)
