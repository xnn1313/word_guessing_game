import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import puzzle_content
from scripts import import_external_puzzle_banks as external_import
import storage


class ExternalPuzzleImportTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        self.sudoku_path = Path(self.temporary_directory.name) / "sudoku.json"
        self.idiom_path = Path(self.temporary_directory.name) / "idiom.json"
        self.original_database_path = storage.DB_PATH
        storage.DB_PATH = str(self.database_path)
        storage.init_db()
        self._write_valid_banks()

    def tearDown(self):
        storage.DB_PATH = self.original_database_path
        self.temporary_directory.cleanup()

    @staticmethod
    def _synthetic_word(index):
        # All generated words are distinct common-Han strings and deliberately
        # avoid the built-in vocabulary.
        digits = []
        value = index
        for _ in range(3):
            digits.append(chr(0x5000 + value % 32))
            value //= 32
        return "共" + "".join(digits)

    def _idiom_payload(self):
        records = [
            {
                "word": "画龙点睛",
                "clue": "这条答案已存在于内置题库，应被过滤。",
                "pinyin": "hua long dian jing",
                "frequency": 999999,
                "source_id": hashlib.sha256("画龙点睛".encode("utf-8")).hexdigest()[:16],
            }
        ]
        # 2000 answers are consumed as 1000 disjoint crossing pairs; one spare
        # record keeps this fixture valid after filtering the built-in answer.
        for index in range(2001):
            word = self._synthetic_word(index)
            records.append(
                {
                    "word": word,
                    "clue": f"测试释义 {index}",
                    "pinyin": "gong test",
                    "frequency": 10000 - index,
                    "source_id": hashlib.sha256(word.encode("utf-8")).hexdigest()[:16],
                }
            )
        return {
            "schema_version": 1,
            "metadata": {"count": len(records), "builder": "test"},
            "idioms": records,
        }

    def _sudoku_payload(self):
        records = []
        counts = {difficulty: 0 for difficulty in external_import.DIFFICULTIES}
        for difficulty, (puzzle, solution) in puzzle_content.SUDOKU_BASES.items():
            transformed_puzzle, transformed_solution = puzzle_content._sudoku_transform(
                puzzle, solution, difficulty, 1000
            )
            source_id = hashlib.sha1(transformed_puzzle.encode("ascii")).hexdigest()[:12]
            records.append(
                {
                    "difficulty": difficulty,
                    "puzzle": transformed_puzzle,
                    "solution": transformed_solution,
                    "rating": 1.0,
                    "source_id": source_id,
                    "source": f"sudoku-exchange:{source_id}",
                }
            )
            counts[difficulty] += 1

        # The importer, rather than the database schema, enforces puzzle-string
        # deduplication.  Include one existing puzzle under a fresh source ID.
        with storage._connect() as connection:
            existing = connection.execute(
                "SELECT difficulty, puzzle, solution FROM sudoku_puzzles ORDER BY id LIMIT 1"
            ).fetchone()
        source_id = hashlib.sha1(existing["puzzle"].encode("ascii")).hexdigest()[:12]
        records.append(
            {
                "difficulty": existing["difficulty"],
                "puzzle": existing["puzzle"],
                "solution": existing["solution"],
                "rating": 2.0,
                "source_id": source_id,
                "source": f"sudoku-exchange:{source_id}",
            }
        )
        counts[existing["difficulty"]] += 1
        return {
            "schema_version": 1,
            "metadata": {"counts": counts, "builder": "test"},
            "puzzles": records,
        }

    def _write_json(self, path, payload):
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

    def _write_valid_banks(self):
        self._write_json(self.sudoku_path, self._sudoku_payload())
        self._write_json(self.idiom_path, self._idiom_payload())

    def _import(self):
        return external_import.import_external_puzzle_banks(
            self.database_path, self.sudoku_path, self.idiom_path
        )

    def test_import_is_insert_only_deduplicated_and_idempotent(self):
        user_id = storage.create_user("import-test-user", "password-hash")
        with storage._connect() as connection:
            old_levels = connection.execute(
                "SELECT id, level_order FROM idiom_puzzles ORDER BY level_order"
            ).fetchall()
            old_first = tuple(
                connection.execute(
                    """
                    SELECT level_order, category, difficulty, title, layout_json,
                           clues_json, solution_json
                    FROM idiom_puzzles WHERE id = 'idiom-001'
                    """
                ).fetchone()
            )

        first = self._import()
        self.assertEqual(first["idiom"]["inserted"], 1000)
        self.assertEqual(first["idiom"]["selected"], 1000)
        self.assertGreaterEqual(first["idiom"]["skipped_existing_answers"], 1)
        self.assertEqual(first["sudoku"]["inserted"], 3)
        self.assertEqual(first["sudoku"]["skipped_duplicate_puzzles"], 1)

        with storage._connect() as connection:
            new_old_levels = connection.execute(
                """
                SELECT id, level_order FROM idiom_puzzles
                WHERE level_order <= 120 ORDER BY level_order
                """
            ).fetchall()
            new_first = tuple(
                connection.execute(
                    """
                    SELECT level_order, category, difficulty, title, layout_json,
                           clues_json, solution_json
                    FROM idiom_puzzles WHERE id = 'idiom-001'
                    """
                ).fetchone()
            )
            external_answer_id = "idiom-ext-" + hashlib.sha256(
                "画龙点睛".encode("utf-8")
            ).hexdigest()[:16]
            duplicate_answer_count = connection.execute(
                "SELECT COUNT(*) FROM idiom_puzzles WHERE id = ?",
                (external_answer_id,),
            ).fetchone()[0]
            category_counts = dict(
                connection.execute(
                    """
                    SELECT category, COUNT(*) FROM idiom_puzzles
                    WHERE id LIKE 'idiom-ext-%' GROUP BY category
                    """
                ).fetchall()
            )
            difficulty_counts = dict(
                connection.execute(
                    """
                    SELECT difficulty, COUNT(*) FROM idiom_puzzles
                    WHERE category = 'curated-01' GROUP BY difficulty
                    """
                ).fetchall()
            )
            external_words = []
            for row in connection.execute(
                """
                SELECT clues_json, solution_json FROM idiom_puzzles
                WHERE id LIKE 'idiom-ext-%'
                """
            ).fetchall():
                entries = json.loads(row["clues_json"])
                solution = json.loads(row["solution_json"])
                external_words.extend(
                    external_import._entry_word(entry, solution) for entry in entries
                )
            user_count = connection.execute(
                "SELECT COUNT(*) FROM users WHERE id = ?", (user_id,)
            ).fetchone()[0]

        self.assertEqual([tuple(row) for row in new_old_levels], [tuple(row) for row in old_levels])
        self.assertEqual(new_first, old_first)
        self.assertEqual(duplicate_answer_count, 0)
        self.assertEqual(category_counts, {key: 100 for key in external_import.IDIOM_CATEGORY_KEYS})
        self.assertEqual(difficulty_counts, {"easy": 35, "medium": 35, "hard": 30})
        self.assertEqual(len(external_words), 2000)
        self.assertEqual(len(set(external_words)), 2000)
        self.assertEqual(user_count, 1)

        second = self._import()
        self.assertEqual(second["idiom"]["inserted"], 0)
        self.assertEqual(second["sudoku"]["inserted"], 0)
        with storage._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM puzzle_catalog_imports"
                ).fetchone()[0],
                2,
            )

    def test_invalid_input_leaves_both_banks_unmodified(self):
        payload = json.loads(self.sudoku_path.read_text(encoding="utf-8"))
        payload["puzzles"][0]["solution"] = "1" * 81
        self._write_json(self.sudoku_path, payload)

        with self.assertRaises(external_import.PuzzleBankImportError):
            self._import()
        with storage._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sudoku_puzzles WHERE id LIKE 'sdkx-%'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM idiom_puzzles WHERE id LIKE 'idiom-ext-%'"
                ).fetchone()[0],
                0,
            )
            self.assertIsNone(
                connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = 'puzzle_catalog_imports'
                    """
                ).fetchone()
            )

    def test_import_requires_complete_builtin_release(self):
        with storage._connect() as connection:
            connection.execute("DELETE FROM idiom_puzzles WHERE id = 'idiom-120'")

        with self.assertRaisesRegex(
            external_import.PuzzleBankImportError, "内置成语 1-120"
        ):
            self._import()

        with storage._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sudoku_puzzles WHERE id LIKE 'sdkx-%'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM idiom_puzzles WHERE id LIKE 'idiom-ext-%'"
                ).fetchone()[0],
                0,
            )

    def test_conflict_and_changed_same_version_never_overwrite(self):
        first = self._import()
        self.assertEqual(first["idiom"]["inserted"], 1000)
        selected_word = self._synthetic_word(0)
        selected_id = "idiom-ext-" + hashlib.sha256(
            selected_word.encode("utf-8")
        ).hexdigest()[:16]
        with storage._connect() as connection:
            before = tuple(
                connection.execute(
                    "SELECT title, layout_json, clues_json, solution_json FROM idiom_puzzles WHERE id = ?",
                    (selected_id,),
                ).fetchone()
            )

        payload = json.loads(self.idiom_path.read_text(encoding="utf-8"))
        payload["idioms"][1]["clue"] = "同版本中被篡改的释义"
        self._write_json(self.idiom_path, payload)
        with self.assertRaises(external_import.PuzzleBankConflictError):
            self._import()

        with storage._connect() as connection:
            after = tuple(
                connection.execute(
                    "SELECT title, layout_json, clues_json, solution_json FROM idiom_puzzles WHERE id = ?",
                    (selected_id,),
                ).fetchone()
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM idiom_puzzles WHERE id LIKE 'idiom-ext-%'"
                ).fetchone()[0],
                1000,
            )
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
