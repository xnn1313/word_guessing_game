"""Deterministic word-search boards and server-authoritative game rules.

The public board intentionally contains only a character grid and clue metadata.
Answers and placements are reconstructed from a signed ``board_id`` for every
save/submit request, so clients cannot award progress by sending entry IDs.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import hmac
import json
import os
from pathlib import Path
import random
import secrets
from typing import Any

import puzzle_games
import storage


PuzzleError = puzzle_games.PuzzleError
DIFFICULTIES = {
    "easy": {"rows": 6, "columns": 6, "word_count": 4},
    "medium": {"rows": 7, "columns": 7, "word_count": 6},
    "hard": {"rows": 8, "columns": 8, "word_count": 8},
}
THEMES = {
    "classic": {
        "title": "成语万花筒",
        "description": "从常用成语中寻找纵横交错的词语",
        "keywords": "",
    },
    "nature": {
        "title": "自然万象",
        "description": "山水风云、四季草木主题",
        "keywords": "天地山水风云雨雪雷电日月星辰春夏秋冬江河湖海花草树木林泉",
    },
    "animals": {
        "title": "动物世界",
        "description": "藏着飞禽走兽的成语",
        "keywords": "龙虎马牛羊犬狗鸡鸟鱼虫蛇兔猴凤鹤狼狐熊猫",
    },
    "character": {
        "title": "品格修养",
        "description": "关于品德、志向与修养的成语",
        "keywords": "德善仁义礼信勇智诚勤廉正坚毅谦忠孝",
    },
    "emotion": {
        "title": "心情百态",
        "description": "寻找表达情绪与感受的成语",
        "keywords": "喜怒哀乐爱恨惊恐悲欢愁忧笑哭心情",
    },
}
DATA_PATH = Path(__file__).with_name("data") / "external_idiom_bank.json"
COMMON_FILLERS = "天地人和山水风云日月星海春秋花木心中大小上下左右东西南北"
MAX_ELAPSED = puzzle_games.MAX_ELAPSED
MAX_MISTAKES = 10000
_DIRECTIONS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),   (1, 1),
)


def themes_catalog() -> dict[str, Any]:
    return {
        "themes": [
            {
                "key": key,
                "title": item["title"],
                "description": item["description"],
            }
            for key, item in THEMES.items()
        ],
        "difficulties": [
            {
                "key": key,
                "rows": item["rows"],
                "columns": item["columns"],
                "word_count": item["word_count"],
            }
            for key, item in DIFFICULTIES.items()
        ],
    }


def _choice(value: Any, allowed: set[str], field: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in allowed:
        raise PuzzleError(f"{field} 参数无效", "INVALID_PARAMETER")
    return normalized


def _integer(data: dict[str, Any], field: str, minimum: int, maximum: int, default: int) -> int:
    value = data.get(field, default)
    if isinstance(value, bool):
        raise PuzzleError(f"{field} 必须是整数", "INVALID_PARAMETER")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise PuzzleError(f"{field} 必须是整数", "INVALID_PARAMETER") from None
    if not minimum <= value <= maximum:
        raise PuzzleError(f"{field} 超出允许范围", "INVALID_PARAMETER")
    return value


@lru_cache(maxsize=1)
def _idiom_records() -> tuple[dict[str, str], ...]:
    try:
        with DATA_PATH.open("r", encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PuzzleError("字阵词库暂时不可用", "PUZZLE_CATALOG_EMPTY", 500) from error
    raw_records = payload.get("idioms") if isinstance(payload, dict) else None
    if not isinstance(raw_records, list):
        raise PuzzleError("字阵词库格式无效", "PUZZLE_CATALOG_EMPTY", 500)
    records = []
    seen = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            continue
        word = raw.get("word")
        clue = raw.get("clue")
        source_id = raw.get("source_id")
        if (
            isinstance(word, str)
            and len(word) == 4
            and all("\u4e00" <= character <= "\u9fff" for character in word)
            and isinstance(clue, str)
            and clue.strip()
            and isinstance(source_id, str)
            and word not in seen
        ):
            seen.add(word)
            records.append({"word": word, "clue": clue.strip(), "source_id": source_id})
    if len(records) < DIFFICULTIES["hard"]["word_count"]:
        raise PuzzleError("字阵词库暂时为空", "PUZZLE_CATALOG_EMPTY", 500)
    return tuple(records)


@lru_cache(maxsize=len(THEMES))
def _theme_records(theme: str) -> tuple[dict[str, str], ...]:
    records = _idiom_records()
    keywords = THEMES[theme]["keywords"]
    if not keywords:
        return records
    themed = tuple(item for item in records if any(char in item["word"] for char in keywords))
    if len(themed) < 32:
        raise PuzzleError("该主题词条不足", "PUZZLE_CATALOG_EMPTY", 500)
    return themed


def _board_secret() -> bytes:
    value = (
        os.environ.get("WORD_SEARCH_BOARD_SECRET")
        or os.environ.get("WORD_GAME_SECRET_KEY")
        or "word-search-development-v1"
    )
    return value.encode("utf-8")


def _sign_board_payload(payload: str) -> str:
    return hmac.new(_board_secret(), payload.encode("ascii"), hashlib.sha256).hexdigest()[:20]


def _issue_board_id(mode: str, difficulty: str, theme: str, seed: str) -> str:
    payload = f"ws1.{mode}.{difficulty}.{theme}.{seed}"
    return f"{payload}.{_sign_board_payload(payload)}"


def _parse_board_id(board_id: Any) -> tuple[str, str, str, str]:
    if not isinstance(board_id, str) or len(board_id) > 160:
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    parts = board_id.split(".")
    if len(parts) != 6 or parts[0] != "ws1":
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    _, mode, difficulty, theme, seed, signature = parts
    if mode not in {"daily", "practice"} or difficulty not in DIFFICULTIES or theme not in THEMES:
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    if not seed or len(seed) > 32 or not seed.isalnum():
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    payload = ".".join(parts[:-1])
    if not hmac.compare_digest(signature, _sign_board_payload(payload)):
        raise PuzzleError("board_id 无效", "PUZZLE_NOT_FOUND", 404)
    return mode, difficulty, theme, seed


def _candidate_placements(
    word: str,
    grid: list[list[str | None]],
    rows: int,
    columns: int,
    rng: random.Random,
) -> list[tuple[float, list[tuple[int, int]]]]:
    candidates = []
    for row in range(rows):
        for column in range(columns):
            for delta_row, delta_column in _DIRECTIONS:
                end_row = row + delta_row * (len(word) - 1)
                end_column = column + delta_column * (len(word) - 1)
                if not (0 <= end_row < rows and 0 <= end_column < columns):
                    continue
                path = [
                    (row + delta_row * offset, column + delta_column * offset)
                    for offset in range(len(word))
                ]
                if any(grid[r][c] not in (None, character) for (r, c), character in zip(path, word)):
                    continue
                crossings = sum(grid[r][c] == character for (r, c), character in zip(path, word))
                # Crossings keep the grid compact; the random component gives
                # deterministic variety for candidates with the same score.
                candidates.append((-crossings, rng.random(), path))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [(tie, path) for _, tie, path in candidates[:48]]


def _place_words(
    words: list[str], rows: int, columns: int, rng: random.Random
) -> tuple[list[list[str | None]], list[list[tuple[int, int]]]] | None:
    grid: list[list[str | None]] = [[None for _ in range(columns)] for _ in range(rows)]
    placements: list[list[tuple[int, int]]] = []

    def place(index: int) -> bool:
        if index == len(words):
            return True
        word = words[index]
        for _, path in _candidate_placements(word, grid, rows, columns, rng):
            changed = []
            for (row, column), character in zip(path, word):
                if grid[row][column] is None:
                    changed.append((row, column))
                    grid[row][column] = character
            placements.append(path)
            if place(index + 1):
                return True
            placements.pop()
            for row, column in changed:
                grid[row][column] = None
        return False

    return (grid, placements) if place(0) else None


def _safe_clue(word: str, clue: str) -> str:
    sanitized = " ".join(clue.split()).replace(word, "□□□□")
    return sanitized[:180]


@lru_cache(maxsize=512)
def _board(board_id: str) -> dict[str, Any]:
    mode, difficulty, theme, seed = _parse_board_id(board_id)
    settings = DIFFICULTIES[difficulty]
    rows = settings["rows"]
    columns = settings["columns"]
    word_count = settings["word_count"]
    digest = hashlib.sha256(board_id.encode("ascii")).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    pool = list(_theme_records(theme))
    rng.shuffle(pool)

    chosen = None
    placed = None
    # Different deterministic slices avoid a single awkward word selection
    # making an otherwise healthy theme unavailable.
    for attempt in range(24):
        start = attempt * word_count
        if start + word_count > len(pool):
            rng.shuffle(pool)
            start = 0
        candidate = pool[start : start + word_count]
        result = _place_words([item["word"] for item in candidate], rows, columns, rng)
        if result:
            chosen, placed = candidate, result
            break
    if chosen is None or placed is None:
        raise PuzzleError("字阵生成失败，请稍后重试", "PUZZLE_GENERATION_FAILED", 500)

    grid, placements = placed
    filler_pool = "".join(item["word"] for item in pool[:80]) + COMMON_FILLERS
    for row in range(rows):
        for column in range(columns):
            if grid[row][column] is None:
                grid[row][column] = rng.choice(filler_pool)

    entries = []
    for index, (item, path) in enumerate(zip(chosen, placements), 1):
        entries.append(
            {
                "id": f"entry-{index}",
                "word": item["word"],
                "clue": _safe_clue(item["word"], item["clue"]),
                "path": tuple(path),
            }
        )
    return {
        "board_id": board_id,
        "mode": mode,
        "difficulty": difficulty,
        "theme": theme,
        "seed": seed,
        "rows": rows,
        "columns": columns,
        "grid": tuple(tuple(str(value) for value in row) for row in grid),
        "entries": tuple(entries),
    }


def _public_path(path: tuple[tuple[int, int], ...] | list[tuple[int, int]]) -> list[dict[str, int]]:
    return [{"row": row, "column": column} for row, column in path]


def _saved_state(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not run:
        return None
    return {
        "found_entry_ids": list(run["state"].get("found_entry_ids", [])),
        "found_paths": list(run["state"].get("found_paths", [])),
        "elapsed_seconds": run["elapsed_seconds"],
        "mistakes": run["mistakes"],
    }


def get_board(
    user: dict[str, Any] | None,
    mode_value: Any,
    difficulty_value: Any,
    theme_value: Any = "classic",
    requested_board_id: Any = None,
    fresh: bool = False,
) -> dict[str, Any]:
    mode = _choice(mode_value, {"daily", "practice"}, "mode")
    difficulty = _choice(difficulty_value, set(DIFFICULTIES), "difficulty")
    theme = _choice(theme_value or "classic", set(THEMES), "theme")
    puzzle_date = None

    if requested_board_id:
        board_id = str(requested_board_id)
        board_mode, board_difficulty, board_theme, seed = _parse_board_id(board_id)
        if (board_mode, board_difficulty, board_theme) != (mode, difficulty, theme):
            raise PuzzleError("board_id 与请求模式不一致", "INVALID_PARAMETER")
        if mode == "daily":
            puzzle_date = f"{seed[:4]}-{seed[4:6]}-{seed[6:8]}"
    elif mode == "daily":
        puzzle_date = puzzle_games.server_date()
        seed = puzzle_date.replace("-", "")
        expected = _issue_board_id(mode, difficulty, theme, seed)
        daily_key = f"{difficulty}:{theme}"
        board_id = storage.get_daily_puzzle_id("word_search", puzzle_date, daily_key)
        board_id = board_id or storage.set_daily_puzzle_id(
            "word_search", puzzle_date, daily_key, expected
        )
    else:
        if user and fresh:
            storage.abandon_word_search_playing_runs(
                user["id"], mode, difficulty, theme
            )
        resumed = (
            storage.get_latest_word_search_playing_run(
                user["id"], mode, difficulty, theme
            )
            if user and not fresh
            else None
        )
        board_id = resumed["puzzle_id"] if resumed else _issue_board_id(
            mode, difficulty, theme, secrets.token_hex(8)
        )

    board = _board(board_id)
    run = puzzle_games._run_for_puzzle(
        user,
        "word_search",
        board_id,
        mode,
        difficulty,
        {"found_entry_ids": [], "found_paths": [], "theme": theme},
    )
    return {
        "board_id": board_id,
        "mode": mode,
        "puzzle_date": puzzle_date,
        "difficulty": difficulty,
        "theme": theme,
        "theme_title": THEMES[theme]["title"],
        "rows": board["rows"],
        "columns": board["columns"],
        "word_count": len(board["entries"]),
        "grid": [list(row) for row in board["grid"]],
        "entries": [
            {"id": item["id"], "clue": item["clue"], "length": len(item["word"])}
            for item in board["entries"]
        ],
        "run_id": run["id"] if run else None,
        "saved_state": _saved_state(run),
    }


def _normalize_path(raw_path: Any, board: dict[str, Any]) -> tuple[tuple[int, int], ...]:
    if not isinstance(raw_path, list) or not 2 <= len(raw_path) <= max(
        board["rows"], board["columns"]
    ):
        raise PuzzleError("坐标路径格式无效", "INVALID_PATH")
    path = []
    for raw_cell in raw_path:
        if isinstance(raw_cell, dict):
            row, column = raw_cell.get("row"), raw_cell.get("column")
        elif isinstance(raw_cell, (list, tuple)) and len(raw_cell) == 2:
            row, column = raw_cell
        else:
            raise PuzzleError("坐标路径格式无效", "INVALID_PATH")
        if isinstance(row, bool) or isinstance(column, bool):
            raise PuzzleError("坐标路径格式无效", "INVALID_PATH")
        try:
            row, column = int(row), int(column)
        except (TypeError, ValueError):
            raise PuzzleError("坐标路径格式无效", "INVALID_PATH") from None
        if not (0 <= row < board["rows"] and 0 <= column < board["columns"]):
            raise PuzzleError("坐标路径超出字阵范围", "INVALID_PATH")
        path.append((row, column))
    if len(set(path)) != len(path):
        raise PuzzleError("坐标路径不能包含重复格子", "INVALID_PATH")
    delta_row = path[1][0] - path[0][0]
    delta_column = path[1][1] - path[0][1]
    if (delta_row, delta_column) not in _DIRECTIONS or any(
        current != (path[0][0] + delta_row * index, path[0][1] + delta_column * index)
        for index, current in enumerate(path)
    ):
        raise PuzzleError("坐标路径必须连续且位于同一直线", "INVALID_PATH")
    return tuple(path)


def _match_path(raw_path: Any, board: dict[str, Any]) -> tuple[dict[str, Any], tuple[tuple[int, int], ...]]:
    path = _normalize_path(raw_path, board)
    text = "".join(board["grid"][row][column] for row, column in path)
    for entry in board["entries"]:
        canonical = entry["path"]
        if path in (canonical, tuple(reversed(canonical))) and text in (
            entry["word"], entry["word"][::-1]
        ):
            return entry, canonical
    raise PuzzleError("所选路径不是本题目标词条", "WORD_NOT_FOUND", 422)


def _validate_found_paths(
    raw_paths: Any, board: dict[str, Any]
) -> tuple[list[str], list[list[dict[str, int]]]]:
    if raw_paths is None:
        raw_paths = []
    if not isinstance(raw_paths, list) or len(raw_paths) > len(board["entries"]):
        raise PuzzleError("found_paths 格式无效", "INVALID_PATH")
    found: dict[str, tuple[tuple[int, int], ...]] = {}
    for raw_path in raw_paths:
        entry, canonical = _match_path(raw_path, board)
        if entry["id"] in found:
            raise PuzzleError("同一词条不能重复提交", "DUPLICATE_PATH")
        found[entry["id"]] = canonical
    entry_order = {entry["id"]: index for index, entry in enumerate(board["entries"])}
    ids = sorted(found, key=entry_order.get)
    paths = [_public_path(found[entry_id]) for entry_id in ids]
    return ids, paths


def _owned_run(
    user: dict[str, Any] | None,
    run_id: Any,
    board_id: str,
    allow_completed: bool = False,
) -> dict[str, Any] | None:
    return puzzle_games._owned_run(
        user, run_id, "word_search", board_id, allow_completed=allow_completed
    )


def save_progress(user: dict[str, Any] | None, data: dict[str, Any]) -> dict[str, Any]:
    if not user:
        raise PuzzleError("请先登录后再保存云端进度", "AUTH_REQUIRED", 401)
    board_id = str(data.get("board_id", ""))
    board = _board(board_id)
    run = _owned_run(user, data.get("run_id"), board_id)
    if not run:
        raise PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    found_ids, found_paths = _validate_found_paths(data.get("found_paths"), board)
    previous_ids = set(run["state"].get("found_entry_ids", []))
    if not previous_ids.issubset(found_ids):
        raise PuzzleError("已找到的词条不能回退", "PROGRESS_REGRESSION")
    elapsed = _integer(data, "elapsed_seconds", 0, MAX_ELAPSED, run["elapsed_seconds"])
    mistakes = _integer(data, "mistakes", 0, MAX_MISTAKES, run["mistakes"])
    timestamp = puzzle_games._save_state(
        run,
        user,
        {"found_entry_ids": found_ids, "found_paths": found_paths, "theme": board["theme"]},
        elapsed,
        0,
        mistakes,
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def _score(difficulty: str, elapsed: int, mistakes: int) -> tuple[int, int]:
    base = {"easy": 1200, "medium": 1700, "hard": 2300}[difficulty]
    score = max(100, base - elapsed * 2 - mistakes * 60)
    three_star_time = {"easy": 180, "medium": 300, "hard": 480}[difficulty]
    stars = 3 if mistakes == 0 and elapsed <= three_star_time else 2 if mistakes <= 2 else 1
    return score, stars


def submit_paths(user: dict[str, Any] | None, data: dict[str, Any]) -> dict[str, Any]:
    board_id = str(data.get("board_id", ""))
    board = _board(board_id)
    run = _owned_run(user, data.get("run_id"), board_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "word_search", board_id)
    if run:
        original = puzzle_games._idempotent_result(run)
        if original:
            return original

    previous_ids: list[str] = []
    previous_paths: list[Any] = []
    if run:
        previous_ids = list(run["state"].get("found_entry_ids", []))
        previous_paths = list(run["state"].get("found_paths", []))
    supplied_paths = data.get("found_paths", previous_paths)
    if "path" in data:
        if not isinstance(supplied_paths, list):
            raise PuzzleError("found_paths 格式无效", "INVALID_PATH")
        supplied_paths = list(supplied_paths) + [data["path"]]

    elapsed_default = run["elapsed_seconds"] if run else 0
    elapsed = _integer(data, "elapsed_seconds", 0, MAX_ELAPSED, elapsed_default)
    if run:
        elapsed = max(elapsed, run["elapsed_seconds"])
    client_mistakes = _integer(
        data, "mistakes", 0, MAX_MISTAKES, run["mistakes"] if run else 0
    )
    try:
        found_ids, found_paths = _validate_found_paths(supplied_paths, board)
    except PuzzleError as error:
        if error.status_code != 422:
            raise
        mistakes = (run["mistakes"] + 1) if run else client_mistakes + 1
        if run:
            puzzle_games._save_state(
                run,
                user,
                {
                    "found_entry_ids": previous_ids,
                    "found_paths": previous_paths,
                    "theme": board["theme"],
                },
                elapsed,
                0,
                mistakes,
            )
        return {
            "correct": False,
            "status": "incorrect",
            "code": error.code,
            "mistakes": mistakes,
        }

    if run and not set(previous_ids).issubset(found_ids):
        raise PuzzleError("已找到的词条不能回退", "PROGRESS_REGRESSION")
    mistakes = max(run["mistakes"] if run else 0, client_mistakes)
    completed = len(found_ids) == len(board["entries"])
    if not completed:
        if run:
            puzzle_games._save_state(
                run,
                user,
                {"found_entry_ids": found_ids, "found_paths": found_paths, "theme": board["theme"]},
                elapsed,
                0,
                mistakes,
            )
        return {
            "correct": True,
            "status": "playing",
            "found_entry_ids": found_ids,
            "found_count": len(found_ids),
            "remaining_count": len(board["entries"]) - len(found_ids),
        }

    score, stars = _score(board["difficulty"], elapsed, mistakes)
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "mistakes": mistakes,
        "found_count": len(found_ids),
        "is_new_best": bool(
            user and puzzle_games._is_new_best(user["id"], "word_search", score)
        ),
    }
    if run:
        did_complete, saved_run = storage.complete_game_run(
            run["id"],
            user["id"],
            {
                "found_entry_ids": found_ids,
                "found_paths": found_paths,
                "theme": board["theme"],
                "result": result,
            },
            elapsed,
            0,
            mistakes,
            score,
            stars,
        )
        if not did_complete:
            return puzzle_games._idempotent_result(saved_run) or {
                "correct": True, "status": "completed", "result": result
            }
    return {"correct": True, "status": "completed", "result": result}
