import os
import tempfile
import unittest
from collections import deque

from flask import Flask, request

import extra_puzzles
import puzzle_api
import storage


class ExtraPuzzleApiTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("extra-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "extra-tester"}

        app = Flask(__name__)
        app.secret_key = "extra-puzzle-test-secret"
        app.testing = True

        def current_user():
            return self.user if request.headers.get("Authorization") == "Bearer test-token" else None

        puzzle_api.register_puzzle_routes(app, current_user)
        self.client = app.test_client()
        self.auth = {"Authorization": "Bearer test-token"}

    def tearDown(self):
        storage.DB_PATH = self.original_db_path
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db_path + suffix)
            except FileNotFoundError:
                pass

    def test_guest_payloads_hide_solutions_and_offer_all_difficulties(self):
        expected_questions = {"easy": 12, "medium": 20, "hard": 30}
        for difficulty, expected_size in (("easy", 5), ("medium", 6), ("hard", 7)):
            poetry = self.client.get(
                f"/api/poetry/quiz?mode=practice&difficulty={difficulty}"
            )
            self.assertEqual(poetry.status_code, 200)
            self.assertIsNone(poetry.json["run_id"])
            self.assertNotIn("answer", poetry.json["question"])
            self.assertEqual(poetry.json["question_count"], expected_questions[difficulty])
            self.assertGreaterEqual(poetry.json["catalog_size"], 300)
            self.assertGreaterEqual(poetry.json["rotation_days"], 30)

            sokoban = self.client.get(
                f"/api/sokoban/board?mode=practice&difficulty={difficulty}"
            )
            self.assertEqual(sokoban.status_code, 200)
            self.assertIsNone(sokoban.json["run_id"])
            self.assertNotIn("solution", sokoban.get_data(as_text=True))

            arrow = self.client.get(
                f"/api/arrow-maze/board?mode=practice&difficulty={difficulty}"
            )
            self.assertEqual(arrow.status_code, 200)
            self.assertEqual(arrow.json["rows"], expected_size)
            self.assertNotIn("solution", arrow.get_data(as_text=True))

    def test_poetry_daily_groups_rotate_without_adjacent_repeats(self):
        for difficulty in extra_puzzles.DIFFICULTIES:
            today = extra_puzzles._select_poetry_group(
                f"poetry-2026-07-20-{difficulty}",
                difficulty,
                extra_puzzles._poetry_pool(difficulty),
                extra_puzzles.POETRY_QUESTION_COUNTS[difficulty],
                extra_puzzles._rng("unused"),
            )
            tomorrow = extra_puzzles._select_poetry_group(
                f"poetry-2026-07-21-{difficulty}",
                difficulty,
                extra_puzzles._poetry_pool(difficulty),
                extra_puzzles.POETRY_QUESTION_COUNTS[difficulty],
                extra_puzzles._rng("unused"),
            )
            self.assertEqual(len(today), len(set(poem[:4] for poem in today)))
            self.assertFalse(set(poem[:4] for poem in today) & set(poem[:4] for poem in tomorrow))

    def test_poetry_cloud_resume_completion_and_idempotency(self):
        payload = self.client.get(
            "/api/poetry/quiz?mode=daily&difficulty=easy", headers=self.auth
        ).json
        questions = extra_puzzles._poetry_questions(payload["puzzle_id"], "easy")
        response = None
        for index, question in enumerate(questions):
            response = self.client.post(
                "/api/poetry/submit",
                headers=self.auth,
                json={
                    "run_id": payload["run_id"],
                    "puzzle_id": payload["puzzle_id"],
                    "difficulty": "easy",
                    "question_id": question["id"],
                    "question_index": index,
                    "answer": question["answer"],
                    "elapsed_seconds": index + 1,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("meaning", response.json["study"])
            self.assertIn("excerpt", response.json["study"])
        self.assertEqual(response.json["status"], "completed")
        self.assertEqual(response.json["result"]["stars"], 3)

        repeated = self.client.post(
            "/api/poetry/submit",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "difficulty": "easy",
                "question_id": questions[-1]["id"],
                "question_index": len(questions) - 1,
                "answer": questions[-1]["answer"],
                "elapsed_seconds": 999,
            },
        )
        self.assertEqual(repeated.json["result"], response.json["result"])
        overview = self.client.get("/api/games/overview", headers=self.auth).json
        entry = next(item for item in overview["games"] if item["key"] == "poetry")
        self.assertTrue(entry["daily_completed"])

    def test_sokoban_and_arrow_level_catalogs_unlock_in_order(self):
        for game_key in ("sokoban", "arrow-maze"):
            catalog = self.client.get(f"/api/{game_key}/catalog", headers=self.auth)
            self.assertEqual(catalog.status_code, 200)
            levels = catalog.json["difficulties"][0]["levels"]
            self.assertEqual(len(levels), extra_puzzles.EXTRA_LEVEL_COUNT)
            self.assertTrue(levels[0]["unlocked"])
            self.assertFalse(levels[1]["unlocked"])
            locked = self.client.get(
                f"/api/{game_key}/board?mode=level&difficulty=easy&level=2", headers=self.auth
            )
            self.assertEqual(locked.status_code, 403)

        sokoban = self.client.get(
            "/api/sokoban/board?mode=level&difficulty=easy&level=1", headers=self.auth
        ).json
        sokoban_level = extra_puzzles._generate_sokoban(sokoban["puzzle_id"], "easy")
        sokoban_solution = self.solve_sokoban(sokoban_level)
        completed = self.client.post(
            "/api/sokoban/submit",
            headers=self.auth,
            json={
                "run_id": sokoban["run_id"],
                "puzzle_id": sokoban["puzzle_id"],
                "difficulty": "easy",
                "history": sokoban_solution,
                "elapsed_seconds": 10,
                "mistakes": 0,
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json["result"]["next_level_order"], 2)
        self.assertEqual(
            self.client.get(
                "/api/sokoban/board?mode=level&difficulty=easy&level=2", headers=self.auth
            ).status_code,
            200,
        )

        arrow = self.client.get(
            "/api/arrow-maze/board?mode=level&difficulty=easy&level=1", headers=self.auth
        ).json
        _, arrow_solution = extra_puzzles._generate_arrow_maze(arrow["puzzle_id"], "easy")
        completed = self.client.post(
            "/api/arrow-maze/submit",
            headers=self.auth,
            json={
                "run_id": arrow["run_id"],
                "puzzle_id": arrow["puzzle_id"],
                "difficulty": "easy",
                "path": arrow_solution,
                "elapsed_seconds": 10,
                "hints_used": 0,
                "mistakes": 0,
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json["result"]["next_level_order"], 2)
        self.assertEqual(
            self.client.get(
                "/api/arrow-maze/board?mode=level&difficulty=easy&level=2", headers=self.auth
            ).status_code,
            200,
        )

    @staticmethod
    def solve_sokoban(level):
        start = (level["player"], tuple(sorted(level["boxes"])))
        queue = deque([(start, "")])
        seen = {start}
        while queue:
            (player, raw_boxes), history = queue.popleft()
            boxes = set(raw_boxes)
            if boxes == level["targets"]:
                return history
            row, column = player
            for code, (dr, dc) in extra_puzzles.MOVE_DELTAS.items():
                target = (row + dr, column + dc)
                if target in level["walls"]:
                    continue
                next_boxes = set(boxes)
                if target in boxes:
                    beyond = (target[0] + dr, target[1] + dc)
                    if beyond in level["walls"] or beyond in boxes:
                        continue
                    next_boxes.remove(target)
                    next_boxes.add(beyond)
                state = (target, tuple(sorted(next_boxes)))
                if state not in seen:
                    seen.add(state)
                    queue.append((state, history + code))
        return None

    def test_sokoban_cloud_allows_undo_and_validates_completion(self):
        payload = self.client.get(
            "/api/sokoban/board?mode=practice&difficulty=easy", headers=self.auth
        ).json
        level = extra_puzzles._generate_sokoban(payload["puzzle_id"], "easy")
        solution = self.solve_sokoban(level)
        self.assertTrue(solution)
        prefix = solution[: max(1, len(solution) // 2)]
        saved = self.client.post(
            "/api/sokoban/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "history": prefix,
                "elapsed_seconds": 5,
                "mistakes": 0,
            },
        )
        self.assertEqual(saved.status_code, 200)
        undone = self.client.post(
            "/api/sokoban/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "history": prefix[:-1],
                "elapsed_seconds": 6,
                "mistakes": 0,
            },
        )
        self.assertEqual(undone.status_code, 200)
        completed = self.client.post(
            "/api/sokoban/submit",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "difficulty": "easy",
                "history": solution,
                "elapsed_seconds": 20,
                "mistakes": 0,
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.assertTrue(completed.json["correct"])

    def test_arrow_maze_hint_undo_and_completion(self):
        payload = self.client.get(
            "/api/arrow-maze/board?mode=practice&difficulty=medium", headers=self.auth
        ).json
        grid, solution = extra_puzzles._generate_arrow_maze(payload["puzzle_id"], "medium")
        hint = self.client.post(
            "/api/arrow-maze/hint",
            json={
                "puzzle_id": payload["puzzle_id"],
                "difficulty": "medium",
                "path": [0],
            },
        )
        self.assertEqual(hint.status_code, 200)
        self.assertIn(hint.json["next_index"], extra_puzzles._arrow_moves(0, grid, 6))

        prefix = solution[:3]
        saved = self.client.post(
            "/api/arrow-maze/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "path": prefix,
                "elapsed_seconds": 5,
                "hints_used": 1,
                "mistakes": 0,
            },
        )
        self.assertEqual(saved.status_code, 200)
        undone = self.client.post(
            "/api/arrow-maze/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "path": [0],
                "elapsed_seconds": 6,
                "hints_used": 1,
                "mistakes": 0,
            },
        )
        self.assertEqual(undone.status_code, 200)
        completed = self.client.post(
            "/api/arrow-maze/submit",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "difficulty": "medium",
                "path": solution,
                "elapsed_seconds": 20,
                "hints_used": 1,
                "mistakes": 0,
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json["result"]["optimal_steps"], len(solution) - 1)


if __name__ == "__main__":
    unittest.main()
