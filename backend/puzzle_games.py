"""Business rules for Sudoku, idiom crossword and memory matching APIs."""

from collections import Counter
from datetime import datetime
import hashlib
import random
import secrets
from zoneinfo import ZoneInfo

import config
import storage
from puzzle_content import IDIOM_CATEGORY_NAMES


DIFFICULTIES = {"easy", "medium", "hard"}
MAX_HINTS = config.PUZZLE_MAX_HINTS
MAX_ELAPSED = config.PUZZLE_MAX_ELAPSED_SECONDS

MEMORY_THEMES = {
    "classic": [
        ("circle", "●"), ("triangle", "▲"), ("square", "■"), ("diamond", "◆"),
        ("star", "★"), ("heart", "♥"), ("moon", "☾"), ("sun", "☀"),
        ("club", "♣"), ("spade", "♠"), ("music", "♪"), ("snow", "❄"),
        ("cloud", "☁"), ("umbrella", "☂"), ("flower", "✿"),
    ],
    "fruit": [
        ("apple", "🍎"), ("banana", "🍌"), ("orange", "🍊"), ("watermelon", "🍉"),
        ("grape", "🍇"), ("strawberry", "🍓"), ("cherry", "🍒"), ("peach", "🍑"),
        ("pear", "🍐"), ("pineapple", "🍍"), ("kiwi", "🥝"), ("lemon", "🍋"),
        ("mango", "🥭"), ("coconut", "🥥"), ("melon", "🍈"),
    ],
    "animal": [
        ("cat", "🐱"), ("dog", "🐶"), ("rabbit", "🐰"), ("panda", "🐼"),
        ("tiger", "🐯"), ("lion", "🦁"), ("monkey", "🐵"), ("fox", "🦊"),
        ("bear", "🐻"), ("koala", "🐨"), ("frog", "🐸"), ("penguin", "🐧"),
        ("owl", "🦉"), ("whale", "🐳"), ("dolphin", "🐬"),
    ],
    "transport": [
        ("car", "🚗"), ("taxi", "🚕"), ("bus", "🚌"), ("trolleybus", "🚎"),
        ("racing_car", "🏎️"), ("police_car", "🚓"), ("ambulance", "🚑"),
        ("fire_engine", "🚒"), ("minibus", "🚐"), ("truck", "🚚"), ("tractor", "🚜"),
        ("scooter", "🛵"), ("bicycle", "🚲"), ("airplane", "✈️"), ("helicopter", "🚁"),
    ],
    "food": [
        ("burger", "🍔"), ("fries", "🍟"), ("pizza", "🍕"), ("hotdog", "🌭"),
        ("sandwich", "🥪"), ("taco", "🌮"), ("burrito", "🌯"), ("popcorn", "🍿"),
        ("rice", "🍚"), ("ramen", "🍜"), ("sushi", "🍣"), ("dumpling", "🥟"),
        ("cookie", "🍪"), ("cake", "🍰"), ("candy", "🍬"),
    ],
    "weather": [
        ("sunny", "☀️"), ("partly_cloudy", "🌤️"), ("cloudy", "☁️"),
        ("rain", "🌧️"), ("storm", "⛈️"), ("snow", "🌨️"), ("wind", "🌬️"),
        ("tornado", "🌪️"), ("fog", "🌫️"), ("rainbow", "🌈"), ("umbrella", "☂️"),
        ("snowman", "☃️"), ("comet", "☄️"), ("droplet", "💧"), ("lightning", "⚡"),
    ],
    "sport": [
        ("soccer", "⚽"), ("basketball", "🏀"), ("football", "🏈"), ("baseball", "⚾"),
        ("softball", "🥎"), ("tennis", "🎾"), ("volleyball", "🏐"), ("rugby", "🏉"),
        ("billiards", "🎱"), ("ping_pong", "🏓"), ("badminton", "🏸"), ("hockey", "🏒"),
        ("cricket", "🏏"), ("ski", "🎿"), ("boxing", "🥊"),
    ],
    "ocean": [
        ("fish", "🐟"), ("tropical_fish", "🐠"), ("blowfish", "🐡"), ("shark", "🦈"),
        ("octopus", "🐙"), ("shell", "🐚"), ("coral", "🪸"), ("crab", "🦀"),
        ("lobster", "🦞"), ("shrimp", "🦐"), ("squid", "🦑"), ("whale", "🐋"),
        ("dolphin", "🐬"), ("seal", "🦭"), ("jellyfish", "🪼"),
    ],
    "space": [
        ("rocket", "🚀"), ("flying_saucer", "🛸"), ("satellite", "🛰️"),
        ("crescent_moon", "🌙"), ("full_moon", "🌕"), ("earth", "🌍"), ("sun_face", "🌞"),
        ("star", "⭐"), ("comet", "☄️"), ("telescope", "🔭"), ("astronaut", "🧑‍🚀"),
        ("alien", "👽"), ("galaxy", "🌌"), ("ringed_planet", "🪐"), ("black_hole", "⚫"),
    ],
    "place": [
        ("house", "🏠"), ("office", "🏢"), ("hospital", "🏥"), ("bank", "🏦"),
        ("hotel", "🏨"), ("school", "🏫"), ("factory", "🏭"), ("castle", "🏰"),
        ("shrine", "⛩️"), ("church", "⛪"), ("mosque", "🕌"), ("tent", "⛺"),
        ("stadium", "🏟️"), ("station", "🚉"), ("tower", "🗼"),
    ],
    "music": [
        ("microphone", "🎤"), ("headphones", "🎧"), ("radio", "📻"), ("saxophone", "🎷"),
        ("accordion", "🪗"), ("guitar", "🎸"), ("keyboard", "🎹"), ("trumpet", "🎺"),
        ("violin", "🎻"), ("drum", "🥁"), ("maracas", "🪇"), ("flute", "🪈"),
        ("notes", "🎶"), ("score", "🎼"), ("bell", "🔔"),
    ],
    "culture": [
        ("lantern", "🏮"), ("fan", "🪭"), ("firecracker", "🧨"), ("mahjong", "🀄"),
        ("tea", "🍵"), ("dumpling", "🥟"), ("mooncake", "🥮"), ("dragon", "🐉"),
        ("lion", "🦁"), ("bamboo", "🎋"), ("knot", "🪢"), ("opera", "🎭"),
        ("scroll", "📜"), ("pagoda", "🏯"), ("kite", "🪁"),
    ],
}

MEMORY_DIMENSIONS = {
    "easy": (4, 4),
    "medium": (4, 5),
    "hard": (5, 6),
}


class PuzzleError(Exception):
    def __init__(self, message, code, status_code=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def server_date():
    return datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()


def _timestamp(value):
    if not value:
        return None
    value = str(value)
    if value.endswith("Z"):
        return value
    return value.replace(" ", "T") + "Z"


def _choice(value, allowed, field):
    normalized = str(value or "").strip().lower()
    if normalized not in allowed:
        raise PuzzleError(f"{field} 参数无效", "INVALID_PARAMETER")
    return normalized


def _integer(data, field, minimum=0, maximum=None, default=None):
    value = data.get(field, default)
    if isinstance(value, bool) or value is None:
        raise PuzzleError(f"{field} 必须是整数", "INVALID_PARAMETER")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise PuzzleError(f"{field} 必须是整数", "INVALID_PARAMETER") from None
    if value < minimum or (maximum is not None and value > maximum):
        raise PuzzleError(f"{field} 超出允许范围", "INVALID_PARAMETER")
    return value


def _elapsed(data):
    return _integer(data, "elapsed_seconds", 0, MAX_ELAPSED, 0)


def _daily_pick(game_key, difficulty, puzzle_ids):
    date = server_date()
    existing = storage.get_daily_puzzle_id(game_key, date, difficulty)
    if existing:
        return existing, date
    if not puzzle_ids:
        raise PuzzleError("题库暂时为空", "PUZZLE_CATALOG_EMPTY", 500)
    digest = hashlib.sha256(f"{game_key}:{date}:{difficulty}".encode("utf-8")).digest()
    selected = puzzle_ids[int.from_bytes(digest[:8], "big") % len(puzzle_ids)]
    return storage.set_daily_puzzle_id(game_key, date, difficulty, selected), date


def _owned_run(user, run_id, game_key, puzzle_id, allow_completed=False):
    if not user:
        if run_id:
            raise PuzzleError("该运行记录需要登录后访问", "AUTH_REQUIRED", 401)
        return None
    if not run_id:
        return None
    run = storage.get_game_run(str(run_id))
    if (
        not run
        or run["user_id"] != user["id"]
        or run["game_key"] != game_key
        or run["puzzle_id"] != puzzle_id
    ):
        raise PuzzleError("运行记录不存在", "RUN_NOT_FOUND", 404)
    if run["status"] == "completed" and not allow_completed:
        raise PuzzleError("该运行记录已经完成", "RUN_ALREADY_COMPLETED", 409)
    return run


def _run_for_puzzle(user, game_key, puzzle_id, mode, difficulty, initial_state):
    if not user:
        return None
    run = storage.get_playing_run(user["id"], game_key, puzzle_id)
    return run or storage.create_game_run(
        user["id"], game_key, puzzle_id, mode, difficulty, initial_state
    )


def _save_state(run, user, state, elapsed, hints, mistakes):
    if elapsed < run["elapsed_seconds"]:
        raise PuzzleError("elapsed_seconds 不能小于已保存值", "PROGRESS_REGRESSION")
    if mistakes < run["mistakes"]:
        raise PuzzleError("mistakes 不能小于已保存值", "PROGRESS_REGRESSION")
    updated, timestamp = storage.update_game_run(
        run["id"], user["id"], state, elapsed, hints, mistakes
    )
    if not updated:
        raise PuzzleError("运行记录状态已发生变化", "RUN_STATE_CONFLICT", 409)
    return timestamp


def _is_new_best(user_id, game_key, score):
    stats = storage.get_game_run_stats(user_id).get(game_key, {})
    best = stats.get("best_score")
    return best is None or score > best


def _idempotent_result(run):
    result = run.get("state", {}).get("result")
    if run.get("status") == "completed" and isinstance(result, dict):
        return {"correct": True, "status": "completed", "result": result}
    return None


def _validate_sudoku_grid(grid, puzzle):
    if not isinstance(grid, str) or len(grid) != 81:
        raise PuzzleError("grid 长度必须为 81", "INVALID_GRID")
    if any(value not in "0123456789" for value in grid):
        raise PuzzleError("grid 只能包含数字 0-9", "INVALID_GRID")
    for index, given in enumerate(puzzle["puzzle"]):
        if given != "0" and grid[index] != given:
            raise PuzzleError("原始给定数字不能修改", "SUDOKU_GIVEN_CHANGED")
    return grid


def _validate_notes(notes):
    if notes is None:
        return {}
    if not isinstance(notes, dict) or len(notes) > 81:
        raise PuzzleError("notes 格式无效", "INVALID_NOTES")
    normalized = {}
    for raw_index, values in notes.items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            raise PuzzleError("notes 索引无效", "INVALID_NOTES") from None
        if not 0 <= index < 81 or not isinstance(values, list) or len(values) > 9:
            raise PuzzleError("notes 内容无效", "INVALID_NOTES")
        digits = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 9:
                raise PuzzleError("notes 只能包含数字 1-9", "INVALID_NOTES")
            if value not in digits:
                digits.append(value)
        normalized[str(index)] = digits
    return normalized


def _sudoku_score(difficulty, elapsed, hints, mistakes):
    base = config.SUDOKU_BASE_SCORES[difficulty]
    score = max(100, base - elapsed - hints * 120 - mistakes * 20)
    threshold = config.SUDOKU_THREE_STAR_SECONDS[difficulty]
    if hints == 0 and elapsed <= threshold:
        stars = 3
    elif hints <= 2 and elapsed <= threshold * 2:
        stars = 2
    else:
        stars = 1
    return score, stars


def get_sudoku(user, mode, difficulty):
    mode = _choice(mode, {"daily", "practice"}, "mode")
    difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
    date = None
    if mode == "daily":
        puzzle_id, date = _daily_pick(
            "sudoku", difficulty, storage.list_sudoku_puzzle_ids(difficulty)
        )
    else:
        resumed = storage.get_latest_playing_run(user["id"], "sudoku", mode, difficulty) if user else None
        if resumed and storage.get_sudoku_puzzle(resumed["puzzle_id"]):
            puzzle_id = resumed["puzzle_id"]
        else:
            candidates = storage.list_sudoku_puzzle_ids(difficulty)
            if user:
                recent = set(storage.get_recent_completed_puzzle_ids(user["id"], "sudoku", difficulty))
                candidates = [item for item in candidates if item not in recent] or candidates
            if not candidates:
                raise PuzzleError("数独题库暂时为空", "PUZZLE_CATALOG_EMPTY", 500)
            puzzle_id = secrets.choice(candidates)
    puzzle = storage.get_sudoku_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("数独题目不存在", "PUZZLE_NOT_FOUND", 404)
    run = _run_for_puzzle(
        user,
        "sudoku",
        puzzle_id,
        mode,
        difficulty,
        {"grid": puzzle["puzzle"], "notes": {}},
    )
    saved = None
    if run:
        saved = {
            "grid": run["state"].get("grid", puzzle["puzzle"]),
            "notes": run["state"].get("notes", {}),
            "elapsed_seconds": run["elapsed_seconds"],
            "hints_used": run["hints_used"],
            "mistakes": run["mistakes"],
        }
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "givens": puzzle["puzzle"],
        "run_id": run["id"] if run else None,
        "saved_state": saved,
        "limits": {"max_hints": MAX_HINTS},
    }


def save_sudoku(user, data):
    if not user:
        raise PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_sudoku_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("数独题目不存在", "PUZZLE_NOT_FOUND", 404)
    run = _owned_run(user, data.get("run_id"), "sudoku", puzzle_id)
    if not run:
        raise PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    grid = _validate_sudoku_grid(data.get("grid"), puzzle)
    notes = _validate_notes(data.get("notes", {}))
    elapsed = _elapsed(data)
    mistakes = _integer(data, "mistakes", 0, 10000, run["mistakes"])
    timestamp = _save_state(
        run, user, {"grid": grid, "notes": notes}, elapsed, run["hints_used"], mistakes
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def hint_sudoku(user, data, guest_hints=0):
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_sudoku_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("数独题目不存在", "PUZZLE_NOT_FOUND", 404)
    grid = _validate_sudoku_grid(data.get("grid"), puzzle)
    run = _owned_run(user, data.get("run_id"), "sudoku", puzzle_id)
    if user and not run:
        run = storage.get_playing_run(user["id"], "sudoku", puzzle_id)
    hints = run["hints_used"] if run else guest_hints
    if hints >= MAX_HINTS:
        raise PuzzleError("本题提示次数已用完", "HINT_LIMIT_REACHED", 403)
    candidates = [index for index, value in enumerate(grid) if value != puzzle["solution"][index]]
    if not candidates:
        raise PuzzleError("当前棋盘已经填写正确", "NO_HINT_AVAILABLE", 409)
    index = candidates[0]
    hints += 1
    if run:
        updated_grid = grid[:index] + puzzle["solution"][index] + grid[index + 1 :]
        notes = dict(run["state"].get("notes", {}))
        notes.pop(str(index), None)
        _save_state(
            run,
            user,
            {"grid": updated_grid, "notes": notes},
            run["elapsed_seconds"],
            hints,
            run["mistakes"],
        )
    return {
        "index": index,
        "row": index // 9,
        "column": index % 9,
        "value": int(puzzle["solution"][index]),
        "hints_used": hints,
        "remaining_hints": MAX_HINTS - hints,
    }


def submit_sudoku(user, data, guest_hints=0):
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_sudoku_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("数独题目不存在", "PUZZLE_NOT_FOUND", 404)
    grid = _validate_sudoku_grid(data.get("grid"), puzzle)
    run = _owned_run(user, data.get("run_id"), "sudoku", puzzle_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "sudoku", puzzle_id)
    if run:
        original = _idempotent_result(run)
        if original:
            return original
    invalid = [index for index, value in enumerate(grid) if value != puzzle["solution"][index]]
    if invalid:
        if run:
            mistakes = max(run["mistakes"] + 1, _integer(data, "mistakes", 0, 10000, 0))
            _save_state(
                run,
                user,
                {"grid": grid, "notes": run["state"].get("notes", {})},
                max(run["elapsed_seconds"], _elapsed(data)),
                run["hints_used"],
                mistakes,
            )
        return {"correct": False, "status": "incorrect", "invalid_cells": invalid}
    elapsed = max(run["elapsed_seconds"] if run else 0, _elapsed(data))
    mistakes = max(run["mistakes"] if run else 0, _integer(data, "mistakes", 0, 10000, 0))
    hints = run["hints_used"] if run else min(guest_hints, MAX_HINTS)
    score, stars = _sudoku_score(puzzle["difficulty"], elapsed, hints, mistakes)
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "mistakes": mistakes,
        "hints_used": hints,
        "is_new_best": bool(user and _is_new_best(user["id"], "sudoku", score)),
    }
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"],
            user["id"],
            {"grid": grid, "notes": {}, "result": result},
            elapsed,
            hints,
            mistakes,
            score,
            stars,
        )
        if not completed:
            return _idempotent_result(saved_run) or {
                "correct": True, "status": "completed", "result": result
            }
    return {"correct": True, "status": "completed", "result": result}


def _idiom_cells(puzzle):
    return puzzle["layout"].get("cells", [])


def _idiom_solution_list(puzzle):
    return [puzzle["solution"][f"{cell['row']},{cell['column']}"] for cell in _idiom_cells(puzzle)]


def _validate_idiom_grid(grid, puzzle):
    cells = _idiom_cells(puzzle)
    if not isinstance(grid, list) or len(grid) != len(cells) or len(grid) > 32:
        raise PuzzleError("grid 长度与题目不匹配", "INVALID_GRID")
    normalized = []
    for value in grid:
        if (
            not isinstance(value, str)
            or len(value) > 1
            or (value and not "\u4e00" <= value <= "\u9fff")
        ):
            raise PuzzleError("grid 每格只能包含一个汉字或空字符串", "INVALID_GRID")
        normalized.append(value)
    solution = _idiom_solution_list(puzzle)
    for index, cell in enumerate(cells):
        if cell.get("type") == "fixed" and normalized[index] != solution[index]:
            raise PuzzleError("固定文字不能修改", "IDIOM_FIXED_CHANGED")
    return normalized


def _idiom_initial_grid(puzzle):
    solution = _idiom_solution_list(puzzle)
    return [solution[index] if cell.get("type") == "fixed" else "" for index, cell in enumerate(_idiom_cells(puzzle))]


def _idiom_unlocked(puzzle, progress, puzzles):
    same_category = [item for item in puzzles if item["category"] == puzzle["category"]]
    same_category.sort(key=lambda item: item["level_order"])
    index = next((i for i, item in enumerate(same_category) if item["id"] == puzzle["id"]), None)
    return index == 0 or (index is not None and same_category[index - 1]["id"] in progress)


def idiom_catalog(user):
    puzzles = storage.list_idiom_puzzles()
    progress = storage.get_idiom_progress(user["id"]) if user else {}
    categories = []
    for category_id, (name, description) in IDIOM_CATEGORY_NAMES.items():
        category_puzzles = [item for item in puzzles if item["category"] == category_id]
        if not category_puzzles:
            continue
        levels = []
        for puzzle in category_puzzles:
            result = progress.get(puzzle["id"], {})
            levels.append(
                {
                    "id": puzzle["id"],
                    "order": puzzle["level_order"],
                    "title": puzzle["title"],
                    "difficulty": puzzle["difficulty"],
                    "unlocked": _idiom_unlocked(puzzle, progress, puzzles),
                    "stars": result.get("stars", 0),
                    "best_score": result.get("best_score"),
                }
            )
        categories.append(
            {
                "id": category_id,
                "name": name,
                "description": description,
                "completed_levels": sum(level["stars"] > 0 for level in levels),
                "total_levels": len(levels),
                "levels": levels,
            }
        )
    return {
        "total_stars": sum(item.get("stars", 0) for item in progress.values()),
        "max_stars": len(puzzles) * 3,
        "categories": categories,
    }


def get_idiom(user, mode, difficulty=None, level_id=None):
    mode = _choice(mode, {"daily", "level"}, "mode")
    date = None
    puzzles = storage.list_idiom_puzzles()
    if mode == "daily":
        difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
        candidates = [item["id"] for item in storage.list_idiom_puzzles(True) if item["difficulty"] == difficulty]
        puzzle_id, date = _daily_pick("idiom", difficulty, candidates)
    else:
        puzzle_id = str(level_id or "")[:80]
        if not puzzle_id:
            raise PuzzleError("level_id 不能为空", "INVALID_PARAMETER")
    puzzle = storage.get_idiom_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("成语题目不存在", "PUZZLE_NOT_FOUND", 404)
    progress = storage.get_idiom_progress(user["id"]) if user else {}
    # Guest progress lives on the mini-program. The catalog exposes only the
    # first level by default, while the client may locally unlock and request
    # later levels. Authenticated users continue to use server-side unlocking.
    if mode == "level" and user and not _idiom_unlocked(puzzle, progress, puzzles):
        raise PuzzleError("请先完成上一关", "LEVEL_LOCKED", 403)
    initial_grid = _idiom_initial_grid(puzzle)
    run = _run_for_puzzle(
        user,
        "idiom",
        puzzle_id,
        mode,
        puzzle["difficulty"],
        {"grid": initial_grid},
    )
    saved = None
    if run:
        saved = {
            "grid": run["state"].get("grid", initial_grid),
            "elapsed_seconds": run["elapsed_seconds"],
            "hints_used": run["hints_used"],
            "mistakes": run["mistakes"],
        }
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "title": puzzle["title"],
        "difficulty": puzzle["difficulty"],
        "size": puzzle["size"],
        "cells": _idiom_cells(puzzle),
        "entries": puzzle["clues"],
        "character_bank": puzzle["layout"].get("character_bank", []),
        "run_id": run["id"] if run else None,
        "saved_state": saved,
        "limits": {"max_hints": MAX_HINTS},
    }


def save_idiom(user, data):
    if not user:
        raise PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_idiom_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("成语题目不存在", "PUZZLE_NOT_FOUND", 404)
    run = _owned_run(user, data.get("run_id"), "idiom", puzzle_id)
    if not run:
        raise PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    grid = _validate_idiom_grid(data.get("grid"), puzzle)
    elapsed = _elapsed(data)
    mistakes = _integer(data, "mistakes", 0, 10000, run["mistakes"])
    timestamp = _save_state(run, user, {"grid": grid}, elapsed, run["hints_used"], mistakes)
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def _entry_cell_indexes(puzzle, entry_id):
    entry = next((item for item in puzzle["clues"] if item.get("id") == entry_id), None)
    if not entry:
        return []
    coordinates = []
    row = entry["start"]["row"]
    column = entry["start"]["column"]
    for offset in range(entry["length"]):
        coordinates.append(
            (row + offset if entry["direction"] == "down" else row,
             column + offset if entry["direction"] == "across" else column)
        )
    cells = _idiom_cells(puzzle)
    return [index for index, cell in enumerate(cells) if (cell["row"], cell["column"]) in coordinates]


def hint_idiom(user, data, guest_hints=0):
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_idiom_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("成语题目不存在", "PUZZLE_NOT_FOUND", 404)
    grid = _validate_idiom_grid(data.get("grid"), puzzle)
    run = _owned_run(user, data.get("run_id"), "idiom", puzzle_id)
    if user and not run:
        run = storage.get_playing_run(user["id"], "idiom", puzzle_id)
    hints = run["hints_used"] if run else guest_hints
    if hints >= MAX_HINTS:
        raise PuzzleError("本题提示次数已用完", "HINT_LIMIT_REACHED", 403)
    solution = _idiom_solution_list(puzzle)
    preferred = _entry_cell_indexes(puzzle, str(data.get("entry_id", ""))[:80])
    all_indexes = preferred + [index for index in range(len(grid)) if index not in preferred]
    index = next((item for item in all_indexes if grid[item] != solution[item]), None)
    if index is None:
        raise PuzzleError("当前题目已经填写正确", "NO_HINT_AVAILABLE", 409)
    hints += 1
    if run:
        updated = list(grid)
        updated[index] = solution[index]
        _save_state(
            run, user, {"grid": updated}, run["elapsed_seconds"], hints, run["mistakes"]
        )
    cell = _idiom_cells(puzzle)[index]
    return {
        "row": cell["row"],
        "column": cell["column"],
        "value": solution[index],
        "hints_used": hints,
        "remaining_hints": MAX_HINTS - hints,
    }


def _idiom_score(elapsed, hints, mistakes):
    score = max(100, config.IDIOM_BASE_SCORE - elapsed - hints * 120 - mistakes * 30)
    stars = 3 if hints == 0 and mistakes <= 1 else 2 if hints <= 2 else 1
    return score, stars


def submit_idiom(user, data, guest_hints=0):
    puzzle_id = str(data.get("puzzle_id", ""))[:80]
    puzzle = storage.get_idiom_puzzle(puzzle_id)
    if not puzzle:
        raise PuzzleError("成语题目不存在", "PUZZLE_NOT_FOUND", 404)
    grid = _validate_idiom_grid(data.get("grid"), puzzle)
    run = _owned_run(user, data.get("run_id"), "idiom", puzzle_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "idiom", puzzle_id)
    if run:
        original = _idempotent_result(run)
        if original:
            return original
    solution = _idiom_solution_list(puzzle)
    invalid = [index for index, value in enumerate(grid) if value != solution[index]]
    if invalid:
        if run:
            mistakes = max(run["mistakes"] + 1, _integer(data, "mistakes", 0, 10000, 0))
            _save_state(
                run,
                user,
                {"grid": grid},
                max(run["elapsed_seconds"], _elapsed(data)),
                run["hints_used"],
                mistakes,
            )
        return {"correct": False, "status": "incorrect", "invalid_cells": invalid}
    elapsed = max(run["elapsed_seconds"] if run else 0, _elapsed(data))
    mistakes = max(run["mistakes"] if run else 0, _integer(data, "mistakes", 0, 10000, 0))
    hints = run["hints_used"] if run else min(guest_hints, MAX_HINTS)
    score, stars = _idiom_score(elapsed, hints, mistakes)
    previous = storage.get_idiom_progress(user["id"]).get(puzzle_id, {}) if user else {}
    puzzles = storage.list_idiom_puzzles()
    same_category = [item for item in puzzles if item["category"] == puzzle["category"]]
    same_category.sort(key=lambda item: item["level_order"])
    position = next(i for i, item in enumerate(same_category) if item["id"] == puzzle_id)
    next_level_id = same_category[position + 1]["id"] if position + 1 < len(same_category) else None
    current_total = sum(
        item.get("stars", 0) for item in storage.get_idiom_progress(user["id"]).values()
    ) if user else 0
    earned_stars = max(0, stars - previous.get("stars", 0))
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "mistakes": mistakes,
        "hints_used": hints,
        "earned_stars": earned_stars,
        "total_stars": current_total + earned_stars if user else stars,
        "next_level_id": next_level_id,
        "is_new_best": bool(user and (not previous.get("best_score") or score > previous["best_score"])),
    }
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"], user["id"], {"grid": grid, "result": result}, elapsed, hints,
            mistakes, score, stars
        )
        if not completed:
            return _idempotent_result(saved_run) or {
                "correct": True, "status": "completed", "result": result
            }
    return {"correct": True, "status": "completed", "result": result}


def _memory_board(board_id, difficulty, theme):
    if theme not in MEMORY_THEMES:
        raise PuzzleError("theme 参数无效", "INVALID_PARAMETER")
    rows, columns = MEMORY_DIMENSIONS[difficulty]
    pair_count = rows * columns // 2
    rng = random.Random(hashlib.sha256(board_id.encode("utf-8")).digest())
    faces = rng.sample(MEMORY_THEMES[theme], pair_count)
    cards = [face for face in faces for _ in range(2)]
    rng.shuffle(cards)
    return rows, columns, [
        {"position": index, "face_key": face[0], "display": face[1]}
        for index, face in enumerate(cards)
    ]


def get_memory(user, mode, difficulty, theme="classic", fresh=False):
    mode = _choice(mode, {"daily", "practice"}, "mode")
    difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
    theme = _choice(theme or "classic", set(MEMORY_THEMES), "theme")
    date = None
    if mode == "daily":
        date = server_date()
        daily_key = f"{difficulty}:{theme}"
        existing = storage.get_daily_puzzle_id("memory", date, daily_key)
        board_id = existing or storage.set_daily_puzzle_id(
            "memory", date, daily_key, f"memory-{date}-{difficulty}-{theme}"
        )
    else:
        if user and fresh:
            storage.abandon_memory_playing_runs(
                user["id"], mode, difficulty, theme
            )
        resumed = (
            storage.get_latest_memory_playing_run(user["id"], mode, difficulty, theme)
            if user and not fresh
            else None
        )
        if resumed:
            board_id = resumed["puzzle_id"]
        else:
            board_id = f"memory-practice-{difficulty}-{theme}-{secrets.token_hex(6)}"
    rows, columns, cards = _memory_board(board_id, difficulty, theme)
    run = _run_for_puzzle(
        user,
        "memory",
        board_id,
        mode,
        difficulty,
        {"matched_positions": [], "moves": 0, "theme": theme},
    )
    saved = None
    if run:
        saved = {
            "matched_positions": run["state"].get("matched_positions", []),
            "moves": run["state"].get("moves", 0),
            "elapsed_seconds": run["elapsed_seconds"],
        }
    return {
        "board_id": board_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "theme": theme,
        "rows": rows,
        "columns": columns,
        "cards": cards,
        "run_id": run["id"] if run else None,
        "saved_state": saved,
    }


def _validate_memory_positions(raw_positions, cards):
    if not isinstance(raw_positions, list) or len(raw_positions) > len(cards):
        raise PuzzleError("matched_positions 格式无效", "INVALID_MATCHES")
    positions = []
    for value in raw_positions:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < len(cards):
            raise PuzzleError("matched_positions 包含越界位置", "INVALID_MATCHES")
        if value in positions:
            raise PuzzleError("matched_positions 不能重复", "INVALID_MATCHES")
        positions.append(value)
    counts = Counter(cards[position]["face_key"] for position in positions)
    if any(count != 2 for count in counts.values()):
        raise PuzzleError("已匹配位置必须由完整配对组成", "INVALID_MATCHES")
    return sorted(positions)


def _memory_context(data):
    board_id = str(data.get("board_id", ""))[:120]
    parts = board_id.split("-")
    difficulty = next((part for part in parts if part in DIFFICULTIES), None)
    theme = next((part for part in parts if part in MEMORY_THEMES), None)
    if not board_id or not difficulty or not theme:
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    rows, columns, cards = _memory_board(board_id, difficulty, theme)
    return board_id, difficulty, theme, rows, columns, cards


def save_memory(user, data):
    if not user:
        raise PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    board_id, _, theme, _, _, cards = _memory_context(data)
    run = _owned_run(user, data.get("run_id"), "memory", board_id)
    if not run:
        raise PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    positions = _validate_memory_positions(data.get("matched_positions"), cards)
    previous = set(run["state"].get("matched_positions", []))
    if not previous.issubset(positions):
        raise PuzzleError("已匹配牌面不能回退", "PROGRESS_REGRESSION")
    moves = _integer(data, "moves", 0, 100000, 0)
    if moves < len(positions) // 2 or moves < run["state"].get("moves", 0):
        raise PuzzleError("moves 不能小于已匹配对数或已保存值", "PROGRESS_REGRESSION")
    elapsed = _elapsed(data)
    timestamp = _save_state(
        run,
        user,
        {"matched_positions": positions, "moves": moves, "theme": theme},
        elapsed,
        0,
        0,
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def _memory_score(pair_count, moves, elapsed):
    score = max(100, config.MEMORY_BASE_SCORE - (moves - pair_count) * 35 - elapsed * 2)
    stars = 3 if moves <= pair_count * 1.5 else 2 if moves <= pair_count * 2.5 else 1
    return score, stars


def submit_memory(user, data):
    board_id, _, theme, rows, columns, cards = _memory_context(data)
    positions = _validate_memory_positions(data.get("matched_positions"), cards)
    run = _owned_run(user, data.get("run_id"), "memory", board_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "memory", board_id)
    if run:
        original = _idempotent_result(run)
        if original:
            return original
    if len(positions) != len(cards):
        return {"correct": False, "status": "incorrect", "unmatched_count": len(cards) - len(positions)}
    pair_count = rows * columns // 2
    moves = _integer(data, "moves", pair_count, 100000, pair_count)
    elapsed = max(run["elapsed_seconds"] if run else 0, _elapsed(data))
    if run and moves < run["state"].get("moves", 0):
        raise PuzzleError("moves 不能小于已保存值", "PROGRESS_REGRESSION")
    score, stars = _memory_score(pair_count, moves, elapsed)
    result = {
        "score": score,
        "stars": stars,
        "moves": moves,
        "elapsed_seconds": elapsed,
        "is_new_best": bool(user and _is_new_best(user["id"], "memory", score)),
    }
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"],
            user["id"],
            {"matched_positions": positions, "moves": moves, "theme": theme, "result": result},
            elapsed,
            0,
            0,
            score,
            stars,
        )
        if not completed:
            return _idempotent_result(saved_run) or {
                "correct": True, "status": "completed", "result": result
            }
    return {"correct": True, "status": "completed", "result": result}


def games_overview(user):
    date = server_date()
    idiom_total = max(1, len(storage.list_idiom_puzzles()))
    if not user:
        return {
            "server_date": date,
            "summary": {
                "available_games": 4,
                "completed_today": 0,
                "total_stars": 0,
                "last_game_key": None,
            },
            "games": [
                {"key": "word", "title": "猜词实验室", "availability": "available", "progress_text": "登录后同步进度", "progress_percent": 0, "best_score": None, "daily_completed": False, "last_played_at": None},
                {"key": "sudoku", "title": "每日数独", "availability": "available", "progress_text": "今日未完成", "progress_percent": 0, "best_score": None, "daily_completed": False, "last_played_at": None},
                {"key": "idiom", "title": "成语填字", "availability": "available", "progress_text": f"0 / {idiom_total} 关", "progress_percent": 0, "best_score": None, "daily_completed": False, "last_played_at": None},
                {"key": "memory", "title": "记忆翻牌", "availability": "available", "progress_text": "尚无记录", "progress_percent": 0, "best_score": None, "daily_completed": False, "last_played_at": None},
            ],
        }

    # Materialize default daily mappings before checking completion flags.
    _daily_pick("sudoku", "medium", storage.list_sudoku_puzzle_ids("medium"))
    idiom_daily = [item["id"] for item in storage.list_idiom_puzzles(True) if item["difficulty"] == "medium"]
    _daily_pick("idiom", "medium", idiom_daily)
    memory_daily_key = "medium:classic"
    if not storage.get_daily_puzzle_id("memory", date, memory_daily_key):
        storage.set_daily_puzzle_id(
            "memory", date, memory_daily_key, f"memory-{date}-medium-classic"
        )

    flags = storage.get_daily_completion_flags(user["id"], date)
    stats = storage.get_game_run_stats(user["id"])
    word = storage.get_word_overview(user["id"])
    idiom_progress = storage.get_idiom_progress(user["id"])
    word_stars = word.get("total_stars", 0) or 0
    total_stars = word_stars + sum(item.get("total_stars", 0) for item in stats.values())
    last_candidates = [(key, _timestamp(value.get("last_played_at"))) for key, value in stats.items()]
    last_candidates.append(("word", _timestamp(word.get("last_played_at"))))
    last_candidates = [(key, value) for key, value in last_candidates if value]
    last_game = max(last_candidates, key=lambda item: item[1])[0] if last_candidates else None

    def game_entry(key, title, progress_text, progress_percent):
        current = stats.get(key, {})
        return {
            "key": key,
            "title": title,
            "availability": "available",
            "progress_text": progress_text,
            "progress_percent": round(progress_percent, 2),
            "best_score": current.get("best_score"),
            "daily_completed": key in flags,
            "last_played_at": _timestamp(current.get("last_played_at")),
        }

    memory_best = stats.get("memory", {}).get("best_moves")
    games = [
        {
            "key": "word",
            "title": "猜词实验室",
            "availability": "available",
            "progress_text": f"{word_stars} / 780 星",
            "progress_percent": round(word_stars / 780 * 100, 2),
            "best_score": None,
            "daily_completed": False,
            "last_played_at": _timestamp(word.get("last_played_at")),
        },
        game_entry("sudoku", "每日数独", "今日已完成" if "sudoku" in flags else "今日未完成", 100 if "sudoku" in flags else 0),
        game_entry("idiom", "成语填字", f"{len(idiom_progress)} / {idiom_total} 关", len(idiom_progress) / idiom_total * 100),
        game_entry("memory", "记忆翻牌", f"最佳 {memory_best} 步" if memory_best is not None else "尚无记录", 0),
    ]
    return {
        "server_date": date,
        "summary": {
            "available_games": 4,
            "completed_today": len(flags & {"sudoku", "idiom", "memory"}),
            "total_stars": total_stars,
            "last_game_key": last_game,
        },
        "games": games,
    }
