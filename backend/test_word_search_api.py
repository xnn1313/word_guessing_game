import os
import tempfile
import unittest

from flask import Flask, request

import puzzle_api
import storage
import word_search


class WordSearchApiTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("word-search-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "word-search-tester"}

        app = Flask(__name__)
        app.secret_key = "word-search-api-test-secret"
        app.testing = True

        def current_user():
            return self.user if request.headers.get("Authorization") == "Bearer test-token" else None

        puzzle_api.register_puzzle_routes(app, current_user)
        self.app = app
        self.client = app.test_client()
        self.auth = {"Authorization": "Bearer test-token"}

    def tearDown(self):
        storage.DB_PATH = self.original_db_path
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(self.db_path + suffix)
            except FileNotFoundError:
                pass

    @staticmethod
    def _public_path(path):
        return [{"row": row, "column": column} for row, column in path]

    def test_theme_catalog_and_difficulty_shapes(self):
        catalog = self.client.get("/api/word-search/themes")
        self.assertEqual(catalog.status_code, 200)
        self.assertGreaterEqual(len(catalog.json["themes"]), 5)
        expected = {
            "easy": (6, 6, 4),
            "medium": (7, 7, 6),
            "hard": (8, 8, 8),
        }
        for difficulty, shape in expected.items():
            with self.subTest(difficulty=difficulty):
                response = self.client.get(
                    f"/api/word-search/board?mode=practice&difficulty={difficulty}&theme=animals"
                )
                self.assertEqual(response.status_code, 200)
                payload = response.json
                self.assertEqual(
                    (payload["rows"], payload["columns"], payload["word_count"]), shape
                )
                self.assertEqual(len(payload["grid"]), shape[0])
                self.assertTrue(all(len(row) == shape[1] for row in payload["grid"]))

    def test_daily_board_is_stable_and_does_not_expose_answers(self):
        path = "/api/word-search/board?mode=daily&difficulty=medium&theme=nature"
        first = self.client.get(path)
        second = self.app.test_client().get(path)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json["board_id"], second.json["board_id"])
        self.assertEqual(first.json["grid"], second.json["grid"])
        self.assertEqual(first.json["entries"], second.json["entries"])

        internal = word_search._board(first.json["board_id"])
        serialized = first.get_data(as_text=True)
        self.assertNotIn("solution", serialized.lower())
        self.assertNotIn("answer", serialized.lower())
        self.assertTrue(all(set(entry) == {"id", "clue", "length"} for entry in first.json["entries"]))
        for entry in internal["entries"]:
            self.assertNotIn(entry["word"], serialized)

    def test_signed_board_id_rejects_client_forgery(self):
        payload = self.client.get(
            "/api/word-search/board?mode=practice&difficulty=easy&theme=classic"
        ).json
        forged = payload["board_id"][:-1] + ("0" if payload["board_id"][-1] != "0" else "1")
        response = self.client.post(
            "/api/word-search/submit",
            json={"board_id": forged, "path": [{"row": 0, "column": index} for index in range(4)]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["code"], "PUZZLE_NOT_FOUND")

    def test_wrong_path_is_422_and_correct_reverse_path_is_accepted(self):
        payload = self.client.get(
            "/api/word-search/board?mode=practice&difficulty=easy&theme=classic"
        ).json
        internal = word_search._board(payload["board_id"])
        target_paths = {
            frozenset(entry["path"])
            for entry in internal["entries"]
        }
        wrong = None
        for row in range(payload["rows"]):
            candidate = tuple((row, column) for column in range(4))
            if frozenset(candidate) not in target_paths:
                wrong = self._public_path(candidate)
                break
        self.assertIsNotNone(wrong)
        incorrect = self.client.post(
            "/api/word-search/submit",
            json={"board_id": payload["board_id"], "path": wrong, "elapsed_seconds": 3},
        )
        self.assertEqual(incorrect.status_code, 422)
        self.assertEqual(incorrect.json["correct"], False)
        self.assertEqual(incorrect.json["code"], "WORD_NOT_FOUND")
        self.assertNotIn("answer", incorrect.json)
        self.assertNotIn("solution", incorrect.json)

        reverse_path = self._public_path(reversed(internal["entries"][0]["path"]))
        correct = self.client.post(
            "/api/word-search/submit",
            json={"board_id": payload["board_id"], "path": reverse_path},
        )
        self.assertEqual(correct.status_code, 200)
        self.assertTrue(correct.json["correct"])
        self.assertEqual(correct.json["found_count"], 1)

    def test_logged_in_cloud_save_restore_completion_and_idempotency(self):
        response = self.client.get(
            "/api/word-search/board?mode=practice&difficulty=medium&theme=character",
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json
        internal = word_search._board(payload["board_id"])
        paths = [self._public_path(entry["path"]) for entry in internal["entries"]]

        found = self.client.post(
            "/api/word-search/submit",
            headers=self.auth,
            json={
                "board_id": payload["board_id"],
                "run_id": payload["run_id"],
                "path": paths[0],
                "elapsed_seconds": 12,
            },
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json["found_count"], 1)

        restored = self.client.get(
            "/api/word-search/board?mode=practice&difficulty=medium&theme=character",
            headers=self.auth,
        ).json
        self.assertEqual(restored["board_id"], payload["board_id"])
        self.assertEqual(restored["run_id"], payload["run_id"])
        self.assertEqual(restored["saved_state"]["found_entry_ids"], ["entry-1"])

        save = self.client.post(
            "/api/word-search/save",
            headers=self.auth,
            json={
                "board_id": payload["board_id"],
                "run_id": payload["run_id"],
                "found_paths": paths[:2],
                "elapsed_seconds": 20,
                "mistakes": 0,
            },
        )
        self.assertEqual(save.status_code, 200)

        complete_body = {
            "board_id": payload["board_id"],
            "run_id": payload["run_id"],
            "found_paths": paths,
            "elapsed_seconds": 90,
            "mistakes": 0,
        }
        completed = self.client.post(
            "/api/word-search/submit", headers=self.auth, json=complete_body
        )
        repeated = self.client.post(
            "/api/word-search/submit",
            headers=self.auth,
            json={**complete_body, "elapsed_seconds": 9999, "mistakes": 99},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json["status"], "completed")
        self.assertEqual(completed.json["result"]["found_count"], 6)
        self.assertEqual(repeated.json, completed.json)
        run = storage.get_game_run(payload["run_id"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["score"], completed.json["result"]["score"])

    def test_logged_in_fresh_practice_abandons_previous_theme_run(self):
        path = "/api/word-search/board?mode=practice&difficulty=easy&theme=nature"
        first = self.client.get(path, headers=self.auth).json
        fresh = self.client.get(f"{path}&fresh=1", headers=self.auth).json

        self.assertNotEqual(fresh["board_id"], first["board_id"])
        self.assertNotEqual(fresh["run_id"], first["run_id"])
        self.assertEqual(storage.get_game_run(first["run_id"])["status"], "abandoned")
        self.assertEqual(storage.get_game_run(fresh["run_id"])["status"], "playing")

    def test_cloud_save_requires_login_and_cannot_forge_entry_ids(self):
        payload = self.client.get(
            "/api/word-search/board?mode=practice&difficulty=easy&theme=emotion"
        ).json
        unauthenticated = self.client.post(
            "/api/word-search/save",
            json={
                "board_id": payload["board_id"],
                "found_entry_ids": ["entry-1", "entry-2", "entry-3", "entry-4"],
                "found_paths": [],
            },
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json["code"], "AUTH_REQUIRED")

    def test_daily_completion_appears_in_games_overview(self):
        payload = self.client.get(
            "/api/word-search/board?mode=daily&difficulty=easy&theme=classic",
            headers=self.auth,
        ).json
        internal = word_search._board(payload["board_id"])
        paths = [self._public_path(entry["path"]) for entry in internal["entries"]]
        completed = self.client.post(
            "/api/word-search/submit",
            headers=self.auth,
            json={
                "board_id": payload["board_id"],
                "run_id": payload["run_id"],
                "found_paths": paths,
                "elapsed_seconds": 30,
                "mistakes": 0,
            },
        )
        self.assertEqual(completed.status_code, 200)
        overview = self.client.get("/api/games/overview", headers=self.auth).json
        entry = next(item for item in overview["games"] if item["key"] == "word_search")
        self.assertTrue(entry["daily_completed"])
        self.assertEqual(entry["progress_percent"], 100)
        self.assertEqual(overview["summary"]["available_games"], 5)


if __name__ == "__main__":
    unittest.main()
