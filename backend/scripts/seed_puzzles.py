#!/usr/bin/env python3
"""Create/upgrade puzzle tables, seed catalogs and optionally verify Sudoku uniqueness."""

import argparse
import os
from pathlib import Path
import sys


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import puzzle_content  # noqa: E402
import storage  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="初始化益智游戏题库")
    parser.add_argument("--database", help="SQLite 数据库路径，默认使用 WORD_GAME_DB_PATH")
    parser.add_argument("--verify", action="store_true", help="逐题验证 300 道数独均为唯一解")
    args = parser.parse_args()
    if args.database:
        storage.DB_PATH = os.path.abspath(args.database)

    storage.init_db()
    with storage._connect() as connection:
        sudoku_rows = connection.execute(
            "SELECT id, difficulty, puzzle FROM sudoku_puzzles WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        idiom_count = connection.execute(
            "SELECT COUNT(*) FROM idiom_puzzles WHERE is_active = 1"
        ).fetchone()[0]

    if args.verify:
        with storage._connect() as connection:
            verification_rows = connection.execute(
                "SELECT id, puzzle, solution FROM sudoku_puzzles WHERE is_active = 1 ORDER BY id"
            ).fetchall()
        invalid = [
            row["id"] for row in verification_rows
            if puzzle_content.count_sudoku_solutions(row["puzzle"]) != 1
            or not puzzle_content.sudoku_solution_valid(row["puzzle"], row["solution"])
        ]
        if invalid:
            raise SystemExit(f"唯一解验证失败: {', '.join(invalid[:10])}")

    difficulty_counts = {}
    for row in sudoku_rows:
        difficulty_counts[row["difficulty"]] = difficulty_counts.get(row["difficulty"], 0) + 1
    print(
        {
            "database": storage.DB_PATH,
            "sudoku": difficulty_counts,
            "idiom_levels": idiom_count,
            "uniqueness_verified": bool(args.verify),
        }
    )


if __name__ == "__main__":
    main()
