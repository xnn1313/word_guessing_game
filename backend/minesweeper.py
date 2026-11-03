"""Minesweeper: seeded daily boards, server-side flood reveal, scoring.

The board is generated once per puzzle and stored in the game run, so every
player of a daily puzzle sees the same minefield.  The first reveal is always
safe: if the player happens to click a mine, that mine is moved to the first
free cell instead of ending the game.
"""

from __future__ import annotations

import hashlib
import random
import secrets
from typing import Any

import puzzle_games as pg
import storage

DIFFICULTY_SPECS = {
    "easy": (9, 9, 10),
    "medium": (12, 12, 22),
    "hard": (16, 16, 40),
}
BASE_SCORES = {"easy": 1000, "medium": 1800, "hard": 2600}
THREE_STAR_SECONDS = {"easy": 180, "medium": 300, "hard": 480}
MAX_CELLS = 256


def _seed_for(puzzle_id: str) -> int:
    digest = hashlib.sha256(f"minesweeper:{puzzle_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _generate_mines(puzzle_id: str, rows: int, cols: int, count: int) -> list[int]:
    rng = random.Random(_seed_for(puzzle_id))
    return sorted(rng.sample(range(rows * cols), count))


def _neighbors(index: int, rows: int, cols: int) -> list[int]:
    row, col = divmod(index, cols)
    result = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if 0 <= r < rows and 0 <= c < cols:
                result.append(r * cols + c)
    return result


def _adjacent_count(index: int, mines: set[int], rows: int, cols: int) -> int:
    return sum(1 for neighbor in _neighbors(index, rows, cols) if neighbor in mines)


def _view(state: dict, rows: int, cols: int, mine_count: int) -> dict:
    mines = set(state["mines"])
    revealed = set(state["revealed"])
    flags = set(state["flags"])
    status = state["status"]
    cells = []
    for index in range(rows * cols):
        if index in revealed:
            cells.append(
                {
                    "index": index,
                    "state": "revealed",
                    "adjacent": _adjacent_count(index, mines, rows, cols),
                }
            )
        elif status == "lost" and index in mines:
            cells.append({"index": index, "state": "mine"})
        elif index in flags:
            cells.append({"index": index, "state": "flagged"})
        else:
            cells.append({"index": index, "state": "hidden"})
    return {
        "rows": rows,
        "cols": cols,
        "mines": mine_count,
        "cells": cells,
        "status": status,
        "first_click": bool(state.get("first_click")),
        "flags": len(flags),
        "remaining_mines": max(0, mine_count - len(flags)),
        "safe_total": rows * cols - mine_count,
        "safe_revealed": len(revealed),
    }


def _new_state(puzzle_id: str, difficulty: str) -> dict:
    rows, cols, mine_count = DIFFICULTY_SPECS[difficulty]
    return {
        "mines": _generate_mines(puzzle_id, rows, cols, mine_count),
        "revealed": [],
        "flags": [],
        "first_click": True,
        "status": "playing",
        "difficulty": difficulty,
    }


def _score(difficulty: str, elapsed: int) -> tuple[int, int]:
    base = BASE_SCORES[difficulty]
    score = max(100, base - int(elapsed) * 2)
    three = THREE_STAR_SECONDS[difficulty]
    stars = 3 if elapsed <= three else 2 if elapsed <= three * 2 else 1
    return score, stars


def _result(state: dict, difficulty: str, elapsed: int, is_new_best: bool) -> dict:
    score, stars = _score(difficulty, elapsed)
    return {
        "score": score,
        "stars": stars,
        "difficulty": difficulty,
        "elapsed_seconds": elapsed,
        "is_new_best": is_new_best,
    }


def start(user, params):
    mode = pg._choice(params.get("mode") or "daily", {"daily", "practice"}, "mode")
    if mode == "daily":
        difficulty = "easy"
        date = pg.server_date()
        puzzle_id = storage.get_daily_puzzle_id("minesweeper", date, "easy")
        if not puzzle_id:
            puzzle_id = storage.set_daily_puzzle_id(
                "minesweeper", date, "easy", f"minesweeper-{date}"
            )
    else:
        difficulty = pg._choice(
            params.get("difficulty") or "easy", set(DIFFICULTY_SPECS), "difficulty"
        )
        date = None
        resume = None
        if user and params.get("fresh") != "1":
            resume = storage.get_latest_playing_run(
                user["id"], "minesweeper", "practice", difficulty
            )
        puzzle_id = (
            resume["puzzle_id"]
            if resume
            else f"minesweeper-practice-{secrets.token_hex(6)}"
        )

    initial_state = _new_state(puzzle_id, difficulty)
    run = pg._run_for_puzzle(
        user, "minesweeper", puzzle_id, mode, difficulty, initial_state
    )
    if run and run["state"].get("status") == "lost":
        storage.update_game_run(run["id"], run["user_id"], initial_state, 0, 0, 0)
        run = storage.get_game_run(run["id"])
    state = run["state"] if run else initial_state
    rows, cols, mine_count = DIFFICULTY_SPECS[difficulty]
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "rows": rows,
        "cols": cols,
        "mines": mine_count,
        "run_id": run["id"] if run else None,
        "elapsed_seconds": run["elapsed_seconds"] if run else 0,
        "view": _view(state, rows, cols, mine_count),
    }


def save(user, data):
    if not user:
        raise pg.PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id", ""))[:120]
    if not puzzle_id:
        raise pg.PuzzleError("puzzle_id 不能为空", "PUZZLE_NOT_FOUND", 404)
    run = pg._owned_run(user, data.get("run_id"), "minesweeper", puzzle_id)
    if not run:
        raise pg.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")

    state = {
        "mines": list(run["state"]["mines"]),
        "revealed": list(run["state"]["revealed"]),
        "flags": list(run["state"]["flags"]),
        "first_click": bool(run["state"].get("first_click")),
        "status": run["state"].get("status", "playing"),
        "difficulty": run["state"].get("difficulty", "easy"),
    }
    difficulty = state["difficulty"]
    rows, cols, mine_count = DIFFICULTY_SPECS[difficulty]
    if state["status"] != "playing":
        raise pg.PuzzleError("本局已经结束", "RUN_FINISHED", 409)

    action = str(data.get("action") or "reveal")
    cell = pg._integer(data, "cell", 0, rows * cols - 1)
    mines = set(state["mines"])
    revealed = set(state["revealed"])
    flags = set(state["flags"])

    if action == "flag":
        if cell in revealed:
            raise pg.PuzzleError("不能标记已翻开的格子", "CELL_REVEALED")
        if cell in flags:
            flags.discard(cell)
        else:
            flags.add(cell)
    elif action == "reveal":
        if cell in flags:
            raise pg.PuzzleError("请先取消标记", "CELL_FLAGGED")
        if cell in revealed:
            raise pg.PuzzleError("格子已经翻开", "CELL_REVEALED")
        if state["first_click"] and cell in mines:
            free = next(index for index in range(rows * cols) if index not in mines)
            mines.discard(cell)
            mines.add(free)
            state["mines"] = sorted(mines)
        state["first_click"] = False
        if cell in mines:
            state["status"] = "lost"
        else:
            stack = [cell]
            while stack:
                current = stack.pop()
                if current in revealed or current in flags:
                    continue
                revealed.add(current)
                if _adjacent_count(current, mines, rows, cols) == 0:
                    stack.extend(_neighbors(current, rows, cols))
        if len(revealed) == rows * cols - mine_count:
            state["status"] = "won"
    else:
        raise pg.PuzzleError("action 只能是 reveal 或 flag", "INVALID_ACTION")

    state["revealed"] = sorted(revealed)
    state["flags"] = sorted(flags)
    elapsed = max(int(run["elapsed_seconds"]), pg._elapsed(data))
    result = None
    if state["status"] == "won":
        result = _result(state, difficulty, elapsed, True)
        storage.complete_game_run(
            run["id"],
            run["user_id"],
            {**state, "result": result},
            elapsed,
            0,
            0,
            result["score"],
            result["stars"],
        )
    else:
        pg._save_state(run, user, state, elapsed, 0, 0)

    return {
        "saved": True,
        "run_id": run["id"],
        "view": _view(state, rows, cols, mine_count),
        "status": state["status"],
        "result": result,
    }


def submit(user, data):
    puzzle_id = str(data.get("puzzle_id", ""))[:120]
    if not puzzle_id:
        raise pg.PuzzleError("puzzle_id 不能为空", "PUZZLE_NOT_FOUND", 404)
    run = pg._owned_run(
        user, data.get("run_id"), "minesweeper", puzzle_id, allow_completed=True
    )
    if not run:
        raise pg.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    original = pg._idempotent_result(run)
    if original:
        return original
    state = run["state"]
    difficulty = state.get("difficulty", "easy")
    rows, cols, mine_count = DIFFICULTY_SPECS[difficulty]
    if state.get("status") != "won":
        return {
            "correct": False,
            "status": state.get("status", "playing"),
            "view": _view(state, rows, cols, mine_count),
        }
    elapsed = max(int(run["elapsed_seconds"]), pg._elapsed(data))
    result = _result(state, difficulty, elapsed, False)
    storage.complete_game_run(
        run["id"],
        run["user_id"],
        {**state, "result": result},
        elapsed,
        0,
        0,
        result["score"],
        result["stars"],
    )
    return {"correct": True, "status": "completed", "result": result}
