"""Tests for the 2048 daily puzzle plugin."""

import os
import tempfile
import unittest

from flask import Flask, request

import puzzle_api
import storage
import tile_2048


class Tile2048TestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("tile-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "tile-tester"}

        app = Flask(__name__)
        app.secret_key = "tile-2048-test-secret"
        app.testing = True

        def current_user():
            if request.headers.get("Authorization") == "Bearer test-token":
                return self.user
            return None

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

    def _start(self, query="mode=daily", auth=True):
        return self.client.get(
            f"/api/games/tile2048/start?{query}",
            headers=self.auth if auth else {},
        )

    def test_daily_board_is_deterministic_and_guest_can_start(self):
        first = self._start(auth=False).json
        second = self._start(auth=False).json
        self.assertEqual(first["puzzle_id"], second["puzzle_id"])
        self.assertEqual(first["board"], second["board"])
        self.assertEqual(len(first["board"]), 16)
        self.assertEqual(first["goal"], 2048)
        self.assertTrue(all(value in (0, 2, 4) for value in first["board"]))

    def test_guest_cannot_save_or_submit_progress(self):
        payload = self._start(auth=False).json
        saved = self.client.post(
            "/api/games/tile2048/save",
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": payload["board"],
                "score": 0,
                "moves": 0,
            },
        )
        self.assertEqual(saved.status_code, 401)
        self.assertEqual(saved.json["code"], "AUTH_REQUIRED")

    def test_save_resumes_progress(self):
        payload = self._start().json
        board = list(payload["board"])
        board[0] = 2
        response = self.client.post(
            "/api/games/tile2048/save",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": board,
                "score": 16,
                "moves": 4,
                "elapsed_seconds": 12,
            },
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json["saved"])
        resumed = self._start().json
        self.assertEqual(resumed["board"], board)
        self.assertEqual(resumed["score"], 16)
        self.assertEqual(resumed["moves"], 4)

    def test_progress_cannot_regress(self):
        payload = self._start().json
        self.client.post(
            "/api/games/tile2048/save",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": payload["board"],
                "score": 40,
                "moves": 6,
            },
        )
        response = self.client.post(
            "/api/games/tile2048/save",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": payload["board"],
                "score": 8,
                "moves": 1,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], "PROGRESS_REGRESSION")

    def test_incomplete_submit_is_422(self):
        payload = self._start().json
        response = self.client.post(
            "/api/games/tile2048/submit",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": payload["board"],
                "score": 32,
                "moves": 5,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json["correct"])
        self.assertEqual(response.json["status"], "incomplete")

    def test_winning_submit_completes_and_is_idempotent(self):
        payload = self._start().json
        winning = [2048] + [0] * 15
        body = {
            "puzzle_id": payload["puzzle_id"],
            "run_id": payload["run_id"],
            "board": winning,
            "score": 5000,
            "moves": 10,
            "elapsed_seconds": 60,
        }
        response = self.client.post("/api/games/tile2048/submit", headers=self.auth, json=body)
        self.assertEqual(response.status_code, 200, response.json)
        result = response.json["result"]
        self.assertEqual(result["best_tile"], 2048)
        self.assertEqual(result["stars"], 2)

        repeated = self.client.post(
            "/api/games/tile2048/submit",
            headers=self.auth,
            json={**body, "score": 9999},
        )
        self.assertEqual(repeated.json, response.json)

        overview = self.client.get("/api/games/overview", headers=self.auth).json
        entry = next(item for item in overview["games"] if item["key"] == "tile2048")
        self.assertTrue(entry["daily_completed"])
        self.assertEqual(entry["best_score"], 5000)

    def test_practice_fresh_starts_a_new_board(self):
        first = self.client.get(
            "/api/games/tile2048/start?mode=practice", headers=self.auth
        ).json
        resumed = self.client.get(
            "/api/games/tile2048/start?mode=practice", headers=self.auth
        ).json
        fresh = self.client.get(
            "/api/games/tile2048/start?mode=practice&fresh=1", headers=self.auth
        ).json
        self.assertEqual(first["puzzle_id"], resumed["puzzle_id"])
        self.assertNotEqual(first["puzzle_id"], fresh["puzzle_id"])

    def test_invalid_board_is_rejected(self):
        payload = self._start().json
        response = self.client.post(
            "/api/games/tile2048/save",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "board": [3] * 16,
                "score": 0,
                "moves": 0,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["code"], "INVALID_BOARD")

    def test_seed_is_stable(self):
        self.assertEqual(
            tile_2048._initial_board("tile2048-2026-11-03"),
            tile_2048._initial_board("tile2048-2026-11-03"),
        )


if __name__ == "__main__":
    unittest.main()
