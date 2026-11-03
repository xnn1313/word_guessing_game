"""2048 rules: deterministic daily boards, state validation and scoring.

The client owns the swipe animation and merge loop; the server owns the daily
seed, progress storage and the completion check.  Board submissions are
validated structurally (16 power-of-two cells) and monotonically (score and
move count can only grow), which is enough for a casual daily puzzle.
"""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any

import puzzle_games as pg
import storage

SIZE = 4
CELLS = SIZE * SIZE
GOAL = 2048
MAX_TILE = 1 << 20
MAX_SCORE = 5_000_000
MAX_MOVES = 1_000_000


def _seed_for(puzzle_id: str) -> int:
    digest = hashlib.sha256(f"tile2048:{puzzle_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _initial_board(puzzle_id: str) -> list[int]:
    rng = random.Random(_seed_for(puzzle_id))
    board = [0] * CELLS
    for _ in range(2):
        empty = [index for index, value in enumerate(board) if value == 0]
        board[rng.choice(empty)] = 4 if rng.random() < 0.1 else 2
    return board


def _validate_board(raw: Any) -> list[int]:
    if not isinstance(raw, list) or len(raw) != CELLS:
        raise pg.PuzzleError("board 必须包含 16 个格子", "INVALID_BOARD")
    board = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, int):
            raise pg.PuzzleError("board 只能包含整数", "INVALID_BOARD")
        if value != 0 and (value < 2 or value & (value - 1) or value > MAX_TILE):
            raise pg.PuzzleError("board 包含非法方块", "INVALID_BOARD")
        board.append(value)
    return board


def _best_score(user) -> int | None:
    if not user:
        return None
    stats = storage.get_game_run_stats(user["id"]).get("tile2048", {})
    return stats.get("best_score")


def start(user, params):
    mode = pg._choice(params.get("mode") or "daily", {"daily", "practice"}, "mode")
    date = pg.server_date() if mode == "daily" else None
    if mode == "daily":
        puzzle_id = storage.get_daily_puzzle_id("tile2048", date, "daily")
        if not puzzle_id:
            puzzle_id = storage.set_daily_puzzle_id(
                "tile2048", date, "daily", f"tile2048-{date}"
            )
    else:
        resume = None
        if user and params.get("fresh") != "1":
            resume = storage.get_latest_playing_run(user["id"], "tile2048", "practice")
        puzzle_id = (
            resume["puzzle_id"]
            if resume
            else f"tile2048-practice-{secrets.token_hex(6)}"
        )

    initial_state = {"board": _initial_board(puzzle_id), "score": 0, "moves": 0}
    run = pg._run_for_puzzle(user, "tile2048", puzzle_id, mode, "normal", initial_state)
    if run and params.get("fresh") == "1":
        storage.update_game_run(run["id"], user["id"], initial_state, 0, 0, 0)
        run = storage.get_game_run(run["id"])

    state = run["state"] if run else initial_state
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "size": SIZE,
        "goal": GOAL,
        "board": state.get("board") or initial_state["board"],
        "score": int(state.get("score") or 0),
        "moves": int(state.get("moves") or 0),
        "run_id": run["id"] if run else None,
        "elapsed_seconds": run["elapsed_seconds"] if run else 0,
        "best_score": _best_score(user),
    }


def save(user, data):
    if not user:
        raise pg.PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id", ""))[:120]
    if not puzzle_id:
        raise pg.PuzzleError("puzzle_id 不能为空", "PUZZLE_NOT_FOUND", 404)
    run = pg._owned_run(user, data.get("run_id"), "tile2048", puzzle_id)
    if not run:
        raise pg.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    board = _validate_board(data.get("board"))
    score = pg._integer(data, "score", 0, MAX_SCORE)
    moves = pg._integer(data, "moves", 0, MAX_MOVES)
    if score < int(run["state"].get("score") or 0) or moves < int(
        run["state"].get("moves") or 0
    ):
        raise pg.PuzzleError("分数或步数不能回退", "PROGRESS_REGRESSION")
    timestamp = pg._save_state(
        run, user, {"board": board, "score": score, "moves": moves}, pg._elapsed(data), 0, 0
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def submit(user, data):
    puzzle_id = str(data.get("puzzle_id", ""))[:120]
    if not puzzle_id:
        raise pg.PuzzleError("puzzle_id 不能为空", "PUZZLE_NOT_FOUND", 404)
    board = _validate_board(data.get("board"))
    score = pg._integer(data, "score", 0, MAX_SCORE)
    moves = pg._integer(data, "moves", 0, MAX_MOVES)
    elapsed = pg._elapsed(data)
    best_tile = max(board)

    run = pg._owned_run(user, data.get("run_id"), "tile2048", puzzle_id, allow_completed=True)
    if run:
        original = pg._idempotent_result(run)
        if original:
            return original

    if best_tile < GOAL:
        if run:
            pg._save_state(
                run,
                user or {"id": run["user_id"]},
                {"board": board, "score": score, "moves": moves},
                max(elapsed, run["elapsed_seconds"]),
                0,
                0,
            )
        return {
            "correct": False,
            "status": "incomplete",
            "best_tile": best_tile,
            "score": score,
        }

    stars = 3 if best_tile >= 4096 else 2
    result = {
        "score": score,
        "stars": stars,
        "best_tile": best_tile,
        "moves": moves,
        "elapsed_seconds": elapsed,
        "is_new_best": bool(user and (not run or (run.get("score") or 0) < score)),
    }
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"],
            run["user_id"],
            {"board": board, "score": score, "moves": moves, "result": result},
            elapsed,
            0,
            0,
            score,
            stars,
        )
        if not completed:
            return pg._idempotent_result(saved_run) or {
                "correct": True,
                "status": "completed",
                "result": result,
            }
    return {"correct": True, "status": "completed", "result": result}
