"""Flask route registration for the puzzle game API surface."""

from flask import jsonify, request, session as flask_session

import puzzle_games


MAX_JSON_BYTES = 64 * 1024


def register_puzzle_routes(app, get_current_user):
    def resolved_user():
        user = get_current_user()
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer ") and not user:
            raise puzzle_games.PuzzleError("登录状态已失效，请重新登录", "INVALID_TOKEN", 401)
        return user

    def error_response(error):
        return jsonify({"error": error.message, "code": error.code}), error.status_code

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
        return int(hints.get(f"{puzzle_games.server_date()}:{game_key}:{puzzle_id}", 0))

    def save_guest_hint(game_key, puzzle_id, count):
        if resolved_user():
            return
        hints = dict(flask_session.get("puzzle_guest_hints", {}))
        if len(hints) > 100:
            hints = {}
        hints[f"{puzzle_games.server_date()}:{game_key}:{puzzle_id}"] = int(count)
        flask_session["puzzle_guest_hints"] = hints

    @app.errorhandler(puzzle_games.PuzzleError)
    def handle_puzzle_error(error):
        return error_response(error)

    @app.errorhandler(500)
    def handle_puzzle_internal_error(error):
        puzzle_prefixes = (
            "/api/games/",
            "/api/sudoku/",
            "/api/idiom/",
            "/api/memory/",
        )
        if request.path.startswith(puzzle_prefixes):
            app.logger.error("益智游戏接口发生未处理错误: %s", error)
            return jsonify({"error": "服务器暂时无法处理请求", "code": "INTERNAL_ERROR"}), 500
        return error

    @app.route("/api/games/overview")
    def puzzle_games_overview():
        return jsonify(puzzle_games.games_overview(resolved_user()))

    @app.route("/api/sudoku/puzzle")
    def sudoku_puzzle():
        return jsonify(
            puzzle_games.get_sudoku(
                resolved_user(), request.args.get("mode"), request.args.get("difficulty")
            )
        )

    @app.route("/api/sudoku/save", methods=["POST"])
    def sudoku_save():
        return jsonify(puzzle_games.save_sudoku(resolved_user(), body()))

    @app.route("/api/sudoku/hint", methods=["POST"])
    def sudoku_hint():
        data = body()
        puzzle_id = str(data.get("puzzle_id", ""))
        result = puzzle_games.hint_sudoku(
            resolved_user(), data, guest_hint_count("sudoku", puzzle_id)
        )
        save_guest_hint("sudoku", puzzle_id, result["hints_used"])
        return jsonify(result)

    @app.route("/api/sudoku/submit", methods=["POST"])
    def sudoku_submit():
        data = body()
        result = puzzle_games.submit_sudoku(
            resolved_user(),
            data,
            guest_hint_count("sudoku", str(data.get("puzzle_id", ""))),
        )
        return jsonify(result), 200 if result.get("correct") else 422

    @app.route("/api/idiom/catalog")
    def idiom_catalog():
        return jsonify(puzzle_games.idiom_catalog(resolved_user()))

    @app.route("/api/idiom/puzzle")
    def idiom_puzzle():
        return jsonify(
            puzzle_games.get_idiom(
                resolved_user(),
                request.args.get("mode"),
                request.args.get("difficulty"),
                request.args.get("level_id"),
            )
        )

    @app.route("/api/idiom/save", methods=["POST"])
    def idiom_save():
        return jsonify(puzzle_games.save_idiom(resolved_user(), body()))

    @app.route("/api/idiom/hint", methods=["POST"])
    def idiom_hint():
        data = body()
        puzzle_id = str(data.get("puzzle_id", ""))
        result = puzzle_games.hint_idiom(
            resolved_user(), data, guest_hint_count("idiom", puzzle_id)
        )
        save_guest_hint("idiom", puzzle_id, result["hints_used"])
        return jsonify(result)

    @app.route("/api/idiom/submit", methods=["POST"])
    def idiom_submit():
        data = body()
        result = puzzle_games.submit_idiom(
            resolved_user(),
            data,
            guest_hint_count("idiom", str(data.get("puzzle_id", ""))),
        )
        return jsonify(result), 200 if result.get("correct") else 422

    @app.route("/api/memory/board")
    def memory_board():
        return jsonify(
            puzzle_games.get_memory(
                resolved_user(),
                request.args.get("mode"),
                request.args.get("difficulty"),
                request.args.get("theme", "classic"),
                request.args.get("fresh") == "1",
            )
        )

    @app.route("/api/memory/save", methods=["POST"])
    def memory_save():
        return jsonify(puzzle_games.save_memory(resolved_user(), body()))

    @app.route("/api/memory/submit", methods=["POST"])
    def memory_submit():
        result = puzzle_games.submit_memory(resolved_user(), body())
        return jsonify(result), 200 if result.get("correct") else 422
