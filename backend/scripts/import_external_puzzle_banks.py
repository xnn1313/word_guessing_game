#!/usr/bin/env python3
"""Explicitly import verified external puzzle banks into an existing database.

This is deliberately an operator-run migration, not part of ``storage.init_db``.
Both input files are fully parsed and validated before the single SQLite write
transaction begins.  Published puzzle IDs are insert-only: an existing ID must
have byte-for-byte equivalent game content or the whole import is rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from puzzle_content import count_sudoku_solutions, sudoku_solution_valid


DEFAULT_DATABASE = Path(
    os.environ.get("WORD_GAME_DB_PATH", BACKEND_DIR / "word_guessing_game.db")
)
DEFAULT_SUDOKU_BANK = BACKEND_DIR / "data" / "external_sudoku_bank.json"
DEFAULT_IDIOM_BANK = BACKEND_DIR / "data" / "external_idiom_bank.json"

SUPPORTED_SCHEMA_VERSION = 1
IDIOM_IMPORT_COUNT = 1000
IDIOM_REQUIRED_ANSWER_COUNT = IDIOM_IMPORT_COUNT * 2
IDIOM_CATEGORY_COUNT = 10
IDIOM_CATEGORY_SIZE = IDIOM_IMPORT_COUNT // IDIOM_CATEGORY_COUNT
IDIOM_FIRST_LEVEL_ORDER = 121
IDIOM_CATEGORY_KEYS = tuple(
    f"curated-{index:02d}" for index in range(1, IDIOM_CATEGORY_COUNT + 1)
)
IDIOM_CATEGORY_TITLES = (
    "词库精选一",
    "词库精选二",
    "词库精选三",
    "词库精选四",
    "词库精选五",
    "词库精选六",
    "词库精选七",
    "词库精选八",
    "词库精选九",
    "词库精选十",
)
DIFFICULTIES = ("easy", "medium", "hard")
SUDOKU_SOURCE_ID_RE = re.compile(r"^[0-9a-f]{12}$")
IDIOM_SOURCE_ID_RE = re.compile(r"^[0-9a-f]{16}$")
DISTRACTOR_CHARACTERS = "天地人心山水风月春秋日月星海云雨花木"


class PuzzleBankImportError(ValueError):
    """Base class for safe, user-facing import failures."""


class PuzzleBankConflictError(PuzzleBankImportError):
    """Raised when an import would mutate already-published content."""


def _reject_json_constant(value: str) -> None:
    raise PuzzleBankImportError(f"JSON 中不允许非有限数值: {value}")


def _load_bank(path: Path, record_key: str) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise PuzzleBankImportError(f"题库文件不存在: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as source:
            payload = json.load(source, parse_constant=_reject_json_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PuzzleBankImportError(f"无法读取题库 {path}: {error}") from error
    if not isinstance(payload, dict):
        raise PuzzleBankImportError(f"{path}: JSON 根节点必须是对象")
    if payload.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise PuzzleBankImportError(
            f"{path}: 仅支持 schema_version={SUPPORTED_SCHEMA_VERSION}"
        )
    if not isinstance(payload.get("metadata"), dict):
        raise PuzzleBankImportError(f"{path}: metadata 必须是对象")
    if not isinstance(payload.get(record_key), list):
        raise PuzzleBankImportError(f"{path}: {record_key} 必须是数组")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return payload, hashlib.sha256(canonical).hexdigest()


def _nonempty_text(value: Any, location: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PuzzleBankImportError(f"{location} 必须是字符串")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise PuzzleBankImportError(f"{location} 不能为空")
    if len(normalized) > maximum:
        raise PuzzleBankImportError(f"{location} 超过最大长度 {maximum}")
    return normalized


def _is_common_han(character: str) -> bool:
    return len(character) == 1 and "\u4e00" <= character <= "\u9fff"


def _validate_sudoku_bank(payload: dict[str, Any], location: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    actual_counts = {difficulty: 0 for difficulty in DIFFICULTIES}

    for index, raw in enumerate(payload["puzzles"]):
        item_location = f"{location}:puzzles[{index}]"
        if not isinstance(raw, dict):
            raise PuzzleBankImportError(f"{item_location} 必须是对象")
        difficulty = raw.get("difficulty")
        if difficulty not in DIFFICULTIES:
            raise PuzzleBankImportError(f"{item_location}.difficulty 非法")
        source_id = raw.get("source_id")
        if not isinstance(source_id, str) or not SUDOKU_SOURCE_ID_RE.fullmatch(source_id):
            raise PuzzleBankImportError(f"{item_location}.source_id 必须是 12 位小写十六进制")
        puzzle_id = f"sdkx-{difficulty}-{source_id}"
        if puzzle_id in seen_ids:
            raise PuzzleBankImportError(f"{item_location}: 重复 source_id/difficulty")
        seen_ids.add(puzzle_id)

        puzzle = raw.get("puzzle")
        solution = raw.get("solution")
        if not isinstance(puzzle, str) or len(puzzle) != 81 or any(
            value not in "0123456789" for value in puzzle
        ):
            raise PuzzleBankImportError(f"{item_location}.puzzle 必须是 81 位数字串")
        expected_source_id = hashlib.sha1(puzzle.encode("ascii")).hexdigest()[:12]
        if source_id != expected_source_id:
            raise PuzzleBankImportError(
                f"{item_location}.source_id 与 Sudoku Exchange 题面哈希不一致"
            )
        if not sudoku_solution_valid(puzzle, solution):
            raise PuzzleBankImportError(f"{item_location}.solution 不是该盘面的有效解")
        if count_sudoku_solutions(puzzle) != 1:
            raise PuzzleBankImportError(f"{item_location}.puzzle 不是唯一解")

        rating = raw.get("rating")
        if (
            isinstance(rating, bool)
            or not isinstance(rating, (int, float))
            or not math.isfinite(rating)
            or rating < 0
        ):
            raise PuzzleBankImportError(f"{item_location}.rating 必须是非负有限数值")
        source = raw.get("source")
        if source != f"sudoku-exchange:{source_id}":
            raise PuzzleBankImportError(f"{item_location}.source 与 source_id 不一致")

        actual_counts[difficulty] += 1
        records.append(
            {
                "id": puzzle_id,
                "difficulty": difficulty,
                "puzzle": puzzle,
                "solution": solution,
            }
        )

    if not records:
        raise PuzzleBankImportError(f"{location}: 数独题库为空")
    metadata_counts = payload["metadata"].get("counts")
    if metadata_counts != actual_counts:
        raise PuzzleBankImportError(
            f"{location}: metadata.counts 与实际记录数不一致"
        )
    return records


def _validate_idiom_bank(payload: dict[str, Any], location: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_words: set[str] = set()
    for index, raw in enumerate(payload["idioms"]):
        item_location = f"{location}:idioms[{index}]"
        if not isinstance(raw, dict):
            raise PuzzleBankImportError(f"{item_location} 必须是对象")
        word = raw.get("word")
        if not isinstance(word, str) or len(word) != 4 or not all(
            _is_common_han(character) for character in word
        ):
            raise PuzzleBankImportError(f"{item_location}.word 必须是四个常用汉字")
        source_id = raw.get("source_id")
        expected_source_id = hashlib.sha256(word.encode("utf-8")).hexdigest()[:16]
        if (
            not isinstance(source_id, str)
            or not IDIOM_SOURCE_ID_RE.fullmatch(source_id)
            or source_id != expected_source_id
        ):
            raise PuzzleBankImportError(f"{item_location}.source_id 与 word 哈希不一致")
        if source_id in seen_ids or word in seen_words:
            raise PuzzleBankImportError(f"{item_location}: 输入题库包含重复成语")
        seen_ids.add(source_id)
        seen_words.add(word)

        clue = _nonempty_text(raw.get("clue"), f"{item_location}.clue", 2000)
        pinyin_raw = raw.get("pinyin", "")
        if not isinstance(pinyin_raw, str) or len(pinyin_raw) > 200:
            raise PuzzleBankImportError(f"{item_location}.pinyin 必须是短字符串")
        pinyin = " ".join(pinyin_raw.strip().split())
        frequency = raw.get("frequency")
        if (
            isinstance(frequency, bool)
            or not isinstance(frequency, (int, float))
            or not math.isfinite(frequency)
            or frequency < 0
        ):
            raise PuzzleBankImportError(f"{item_location}.frequency 必须是非负有限数值")
        records.append(
            {
                "source_id": source_id,
                "word": word,
                "clue": clue,
                "pinyin": pinyin,
                "frequency": frequency,
            }
        )

    metadata_count = payload["metadata"].get("count")
    if metadata_count != len(records):
        raise PuzzleBankImportError(f"{location}: metadata.count 与实际记录数不一致")
    if len(records) < IDIOM_REQUIRED_ANSWER_COUNT:
        raise PuzzleBankImportError(
            f"{location}: 至少需要 {IDIOM_REQUIRED_ANSWER_COUNT} 条成语供去重配对"
        )
    return records


def _database_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _entry_word(entry: Any, solution: Any) -> str | None:
    if not isinstance(entry, dict) or not isinstance(solution, dict):
        return None
    start = entry.get("start")
    direction = entry.get("direction")
    length = entry.get("length")
    if (
        not isinstance(start, dict)
        or direction not in {"across", "down"}
        or length != 4
        or not isinstance(start.get("row"), int)
        or not isinstance(start.get("column"), int)
    ):
        return None
    row = start["row"]
    column = start["column"]
    characters = []
    for offset in range(length):
        current_row = row + (offset if direction == "down" else 0)
        current_column = column + (offset if direction == "across" else 0)
        value = solution.get(f"{current_row},{current_column}")
        if not isinstance(value, str) or not _is_common_han(value):
            return None
        characters.append(value)
    return "".join(characters)


def _non_external_idiom_answers(connection: sqlite3.Connection) -> set[str]:
    answers: set[str] = set()
    rows = connection.execute(
        """
        SELECT id, clues_json, solution_json
        FROM idiom_puzzles
        WHERE id NOT LIKE 'idiom-ext-%'
        """
    ).fetchall()
    for row in rows:
        try:
            entries = json.loads(row["clues_json"])
            solution = json.loads(row["solution_json"])
        except (TypeError, json.JSONDecodeError) as error:
            raise PuzzleBankConflictError(
                f"现有成语题 {row['id']} 的 JSON 无法解析，拒绝导入"
            ) from error
        if not isinstance(entries, list):
            raise PuzzleBankConflictError(
                f"现有成语题 {row['id']} 的 clues_json 非法，拒绝导入"
            )
        for entry in entries:
            word = _entry_word(entry, solution)
            if word:
                answers.add(word)
    return answers


def _stable_shuffle(values: list[str], seed: str) -> list[str]:
    indexed = list(enumerate(values))
    indexed.sort(
        key=lambda item: hashlib.sha256(
            f"{seed}:{item[0]}:{item[1]}".encode("utf-8")
        ).digest()
    )
    return [value for _, value in indexed]


def _idiom_layout(
    primary: dict[str, Any], partner: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    word = primary["word"]
    partner_word = partner["word"]
    shared = next((character for character in word if character in partner_word), None)
    if shared is None:
        raise PuzzleBankImportError(f"成语 {word} 与 {partner_word} 没有交叉字")
    across_row = partner_word.index(shared)
    down_column = word.index(shared)
    values: dict[tuple[int, int], str] = {}
    for column, character in enumerate(word):
        values[(across_row, column)] = character
    for row, character in enumerate(partner_word):
        values[(row, down_column)] = character
    fixed_position = (across_row, 0)
    cells: list[dict[str, Any]] = []
    solution: dict[str, str] = {}
    for row, column in sorted(values):
        character = values[(row, column)]
        cell: dict[str, Any] = {
            "row": row,
            "column": column,
            "type": "fixed" if (row, column) == fixed_position else "input",
        }
        if cell["type"] == "fixed":
            cell["value"] = character
        cells.append(cell)
        solution[f"{row},{column}"] = character

    entries = [
        {
            "id": "entry-1",
            "direction": "across",
            "start": {"row": across_row, "column": 0},
            "length": 4,
            "clue": primary["clue"],
            "pinyin_hint": primary["pinyin"] or "· · · ·",
        },
        {
            "id": "entry-2",
            "direction": "down",
            "start": {"row": 0, "column": down_column},
            "length": 4,
            "clue": partner["clue"],
            "pinyin_hint": partner["pinyin"] or "· · · ·",
        },
    ]
    input_characters = [
        solution[f"{cell['row']},{cell['column']}"]
        for cell in cells
        if cell["type"] == "input"
    ]
    distractors = [
        character
        for character in DISTRACTOR_CHARACTERS
        if character not in set(solution.values())
    ][:4]
    character_bank = _stable_shuffle(
        input_characters + distractors, f"idiom-ext:{primary['source_id']}"
    )
    return {"cells": cells, "character_bank": character_bank}, entries, solution


def _difficulty_for_category_position(position: int) -> str:
    if position < 35:
        return "easy"
    if position < 70:
        return "medium"
    return "hard"


def _pair_unique_idioms(
    records: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Deterministically make disjoint crossing pairs in source order.

    The builder orders source records deterministically.  For each still-free
    primary answer, the first later still-free answer sharing a character is
    selected.  A record is removed as soon as it is used, so no answer can
    appear in two imported levels.
    """
    used: set[int] = set()
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for primary_index, primary in enumerate(records):
        if primary_index in used:
            continue
        partner_index = next(
            (
                candidate_index
                for candidate_index in range(primary_index + 1, len(records))
                if candidate_index not in used
                and any(
                    character in records[candidate_index]["word"]
                    for character in primary["word"]
                )
            ),
            None,
        )
        if partner_index is None:
            continue
        used.add(primary_index)
        used.add(partner_index)
        pairs.append((primary, records[partner_index]))
        if len(pairs) == IDIOM_IMPORT_COUNT:
            return pairs
    raise PuzzleBankImportError(
        "成语题库过滤已有答案并进行无复用交叉配对后不足 "
        f"{IDIOM_IMPORT_COUNT} 关（仅得到 {len(pairs)} 对）"
    )


def _plan_sudoku_rows(
    connection: sqlite3.Connection, records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    existing_rows = connection.execute(
        "SELECT id, difficulty, puzzle, solution FROM sudoku_puzzles"
    ).fetchall()
    existing_by_id = {row["id"]: row for row in existing_rows}
    ids_by_puzzle: dict[str, set[str]] = {}
    for row in existing_rows:
        ids_by_puzzle.setdefault(row["puzzle"], set()).add(row["id"])

    planned: list[dict[str, Any]] = []
    skipped_duplicates = 0
    planned_puzzles: set[str] = set()
    for record in records:
        existing = existing_by_id.get(record["id"])
        if existing is not None:
            actual = (existing["difficulty"], existing["puzzle"], existing["solution"])
            expected = (record["difficulty"], record["puzzle"], record["solution"])
            if actual != expected:
                raise PuzzleBankConflictError(
                    f"已发布数独 {record['id']} 与导入内容不同，拒绝覆盖"
                )
        puzzle_ids = ids_by_puzzle.get(record["puzzle"], set())
        if record["puzzle"] in planned_puzzles or (
            puzzle_ids and record["id"] not in puzzle_ids
        ):
            skipped_duplicates += 1
            continue
        if len(puzzle_ids) > 1:
            raise PuzzleBankConflictError(
                f"数据库已有重复数独盘面（包含 {record['id']}），请先人工检查"
            )
        planned.append(record)
        planned_puzzles.add(record["puzzle"])
    return planned, skipped_duplicates


def _plan_idiom_rows(
    connection: sqlite3.Connection, records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    existing_answers = _non_external_idiom_answers(connection)
    eligible = [record for record in records if record["word"] not in existing_answers]
    skipped_duplicates = len(records) - len(eligible)
    if len(eligible) < IDIOM_REQUIRED_ANSWER_COUNT:
        raise PuzzleBankImportError(
            "成语题库去除数据库已有答案后不足 "
            f"{IDIOM_REQUIRED_ANSWER_COUNT} 条（剩余 {len(eligible)} 条）"
        )
    pairs = _pair_unique_idioms(eligible)

    planned: list[dict[str, Any]] = []
    for index, (primary, partner) in enumerate(pairs):
        category_index, category_position = divmod(index, IDIOM_CATEGORY_SIZE)
        layout, entries, solution = _idiom_layout(primary, partner)
        planned.append(
            {
                "id": f"idiom-ext-{primary['source_id']}",
                "level_order": IDIOM_FIRST_LEVEL_ORDER + index,
                "category": IDIOM_CATEGORY_KEYS[category_index],
                "difficulty": _difficulty_for_category_position(category_position),
                "title": f"{IDIOM_CATEGORY_TITLES[category_index]} {category_position + 1}",
                "size": 4,
                "layout_json": _database_json(layout),
                "clues_json": _database_json(entries),
                "solution_json": _database_json(solution),
            }
        )

    existing_by_id = {
        row["id"]: row
        for row in connection.execute(
            """
            SELECT id, level_order, category, difficulty, title, size,
                   layout_json, clues_json, solution_json
            FROM idiom_puzzles
            WHERE id LIKE 'idiom-ext-%'
            """
        ).fetchall()
    }
    occupied_orders = {
        row["level_order"]: row["id"]
        for row in connection.execute(
            "SELECT id, level_order FROM idiom_puzzles WHERE level_order IS NOT NULL"
        ).fetchall()
    }
    compare_keys = (
        "level_order",
        "category",
        "difficulty",
        "title",
        "size",
        "layout_json",
        "clues_json",
        "solution_json",
    )
    for record in planned:
        occupied_id = occupied_orders.get(record["level_order"])
        if occupied_id is not None and occupied_id != record["id"]:
            raise PuzzleBankConflictError(
                f"成语关卡顺序 {record['level_order']} 已被 {occupied_id} 占用"
            )
        existing = existing_by_id.get(record["id"])
        if existing is None:
            continue
        if any(existing[key] != record[key] for key in compare_keys):
            raise PuzzleBankConflictError(
                f"已发布成语 {record['id']} 与导入内容不同，拒绝覆盖"
            )
    return planned, skipped_duplicates


def _result_checksum(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_database_json(rows).encode("utf-8")).hexdigest()


def _check_database_schema(connection: sqlite3.Connection) -> None:
    required = {
        "sudoku_puzzles": {"id", "difficulty", "puzzle", "solution"},
        "idiom_puzzles": {
            "id",
            "level_order",
            "category",
            "difficulty",
            "title",
            "size",
            "layout_json",
            "clues_json",
            "solution_json",
        },
    }
    for table, columns in required.items():
        actual = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not columns <= actual:
            raise PuzzleBankImportError(
                f"数据库缺少 {table} 表或所需字段，请先运行正常的小型种子迁移"
            )


def _require_builtin_idiom_release(connection: sqlite3.Connection) -> None:
    """Prevent importing before the immutable built-in 1-120 release exists."""
    rows = connection.execute(
        """
        SELECT id, level_order FROM idiom_puzzles
        WHERE level_order BETWEEN 1 AND 120
        ORDER BY level_order
        """
    ).fetchall()
    expected = [(f"idiom-{order:03d}", order) for order in range(1, 121)]
    actual = [(row["id"], row["level_order"]) for row in rows]
    if actual != expected:
        raise PuzzleBankImportError(
            "数据库尚未完整安装内置成语 1-120 关；请先运行 "
            "scripts/seed_puzzles.py --verify，再导入外部题库"
        )


def _ensure_import_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS puzzle_catalog_imports (
            bank_kind TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            payload_sha256 TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,
            item_count INTEGER NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (bank_kind, schema_version)
        )
        """
    )


def _verify_batch(
    connection: sqlite3.Connection,
    bank_kind: str,
    payload_sha256: str,
    result_sha256: str,
    item_count: int,
) -> bool:
    row = connection.execute(
        """
        SELECT payload_sha256, result_sha256, item_count
        FROM puzzle_catalog_imports
        WHERE bank_kind = ? AND schema_version = ?
        """,
        (bank_kind, SUPPORTED_SCHEMA_VERSION),
    ).fetchone()
    if row is None:
        return False
    if row["payload_sha256"] != payload_sha256:
        raise PuzzleBankConflictError(
            f"{bank_kind} schema_version={SUPPORTED_SCHEMA_VERSION} 的题库内容已改变；"
            "请提升题库 schema_version，不能覆盖同版本批次"
        )
    if row["result_sha256"] != result_sha256 or row["item_count"] != item_count:
        raise PuzzleBankConflictError(
            f"{bank_kind} 已导入批次与当前数据库筛选结果不一致，拒绝漂移"
        )
    return True


def _record_batch(
    connection: sqlite3.Connection,
    bank_kind: str,
    payload_sha256: str,
    result_sha256: str,
    item_count: int,
) -> None:
    connection.execute(
        """
        INSERT INTO puzzle_catalog_imports (
            bank_kind, schema_version, payload_sha256, result_sha256, item_count
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            bank_kind,
            SUPPORTED_SCHEMA_VERSION,
            payload_sha256,
            result_sha256,
            item_count,
        ),
    )


def import_external_puzzle_banks(
    database_path: str | os.PathLike[str] = DEFAULT_DATABASE,
    sudoku_bank_path: str | os.PathLike[str] = DEFAULT_SUDOKU_BANK,
    idiom_bank_path: str | os.PathLike[str] = DEFAULT_IDIOM_BANK,
) -> dict[str, Any]:
    """Validate and atomically import both external banks.

    The database must already have been initialized by the application.  This
    function never calls ``init_db`` and never updates/deletes a puzzle or any
    user-owned row.
    """
    database = Path(database_path).resolve()
    sudoku_path = Path(sudoku_bank_path).resolve()
    idiom_path = Path(idiom_bank_path).resolve()
    if not database.is_file():
        raise PuzzleBankImportError(f"数据库不存在: {database}")

    sudoku_payload, sudoku_payload_sha = _load_bank(sudoku_path, "puzzles")
    idiom_payload, idiom_payload_sha = _load_bank(idiom_path, "idioms")
    sudoku_records = _validate_sudoku_bank(sudoku_payload, sudoku_path)
    idiom_records = _validate_idiom_bank(idiom_payload, idiom_path)

    connection = sqlite3.connect(database, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        _check_database_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        _require_builtin_idiom_release(connection)
        _ensure_import_table(connection)
        sudoku_rows, sudoku_skipped = _plan_sudoku_rows(connection, sudoku_records)
        idiom_rows, idiom_skipped = _plan_idiom_rows(connection, idiom_records)
        sudoku_result_sha = _result_checksum(sudoku_rows)
        idiom_result_sha = _result_checksum(idiom_rows)
        sudoku_recorded = _verify_batch(
            connection,
            "sudoku",
            sudoku_payload_sha,
            sudoku_result_sha,
            len(sudoku_rows),
        )
        idiom_recorded = _verify_batch(
            connection,
            "idiom",
            idiom_payload_sha,
            idiom_result_sha,
            len(idiom_rows),
        )

        inserted_sudoku = 0
        for record in sudoku_rows:
            cursor = connection.execute(
                """
                INSERT INTO sudoku_puzzles (id, difficulty, puzzle, solution)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    record["id"],
                    record["difficulty"],
                    record["puzzle"],
                    record["solution"],
                ),
            )
            inserted_sudoku += max(cursor.rowcount, 0)

        inserted_idiom = 0
        for record in idiom_rows:
            cursor = connection.execute(
                """
                INSERT INTO idiom_puzzles (
                    id, level_order, category, difficulty, title, size,
                    layout_json, clues_json, solution_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    record["id"],
                    record["level_order"],
                    record["category"],
                    record["difficulty"],
                    record["title"],
                    record["size"],
                    record["layout_json"],
                    record["clues_json"],
                    record["solution_json"],
                ),
            )
            inserted_idiom += max(cursor.rowcount, 0)

        if not sudoku_recorded:
            _record_batch(
                connection,
                "sudoku",
                sudoku_payload_sha,
                sudoku_result_sha,
                len(sudoku_rows),
            )
        if not idiom_recorded:
            _record_batch(
                connection,
                "idiom",
                idiom_payload_sha,
                idiom_result_sha,
                len(idiom_rows),
            )
        connection.commit()
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        connection.close()

    return {
        "database": str(database),
        "idiom": {
            "inserted": inserted_idiom,
            "selected": len(idiom_rows),
            "skipped_existing_answers": idiom_skipped,
        },
        "sudoku": {
            "inserted": inserted_sudoku,
            "selected": len(sudoku_rows),
            "skipped_duplicate_puzzles": sudoku_skipped,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将已构建的外部数独/成语题库一次性导入现有 SQLite 数据库。"
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--sudoku-bank", type=Path, default=DEFAULT_SUDOKU_BANK)
    parser.add_argument("--idiom-bank", type=Path, default=DEFAULT_IDIOM_BANK)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_external_puzzle_banks(
        args.database, args.sudoku_bank, args.idiom_bank
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, sqlite3.Error, PuzzleBankImportError) as error:
        raise SystemExit(f"error: {error}") from error
