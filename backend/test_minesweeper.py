"""Tests for the daily minesweeper plugin."""

import os
import tempfile
import unittest

from flask import Flask, request

import minesweeper
import puzzle_api
import storage


class MinesweeperTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("mine-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "mine-tester"}

        app = Flask(__name__)
        app.secret_key = "minesweeper-test-secret"
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
            f"/api/games/minesweeper/start?{query}",
            headers=self.auth if auth else {},
        ).json

    def _save(self, payload, cell, action="reveal", elapsed=1):
        return self.client.post(
            "/api/games/minesweeper/save",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "action": action,
                "cell": cell,
                "elapsed_seconds": elapsed,
            },
        )

    def _mines(self, run_id):
        return set(storage.get_game_run(run_id)["state"]["mines"])

    def test_guest_and_logged_in_boards(self):
        guest = self._start(auth=False)
        self.assertEqual(guest["rows"], 9)
        self.assertEqual(guest["cols"], 9)
        self.assertEqual(len(guest["view"]["cells"]), 81)
        self.assertEqual(guest["view"]["status"], "playing")

        payload = self._start()
        self.assertIsNotNone(payload["run_id"])
        self.assertEqual(payload["view"]["remaining_mines"], 10)

    def test_guest_cannot_save(self):
        payload = self._start(auth=False)
        response = self.client.post(
            "/api/games/minesweeper/save",
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "action": "reveal",
                "cell": 0,
            },
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "AUTH_REQUIRED")

    def test_first_click_is_safe_even_on_a_mine(self):
        payload = self._start()
        mine = min(self._mines(payload["run_id"]))
        response = self._save(payload, mine)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertNotEqual(response.json["status"], "lost")
        self.assertEqual(response.json["view"]["status"], "playing")
        self.assertNotIn(mine, self._mines(payload["run_id"]))

    def test_flag_toggles_and_persists(self):
        payload = self._start()
        mine = min(self._mines(payload["run_id"]))
        flagged = self._save(payload, mine, action="flag")
        self.assertEqual(flagged.status_code, 200, flagged.json)
        self.assertEqual(flagged.json["view"]["flags"], 1)
        self.assertEqual(flagged.json["view"]["remaining_mines"], 9)

        unflagged = self._save(payload, mine, action="flag")
        self.assertEqual(unflagged.json["view"]["flags"], 0)
        self.assertEqual(unflagged.json["view"]["remaining_mines"], 10)

    def test_hitting_a_mine_loses_without_completing(self):
        payload = self._start()
        mines = self._mines(payload["run_id"])
        safe_cell = next(index for index in range(81) if index not in mines)
        self._save(payload, safe_cell)
        response = self._save(payload, min(mines))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["status"], "lost")

        overview = self.client.get("/api/games/overview", headers=self.auth).json
        entry = next(item for item in overview["games"] if item["key"] == "minesweeper")
        self.assertFalse(entry["daily_completed"])

        restarted = self._start()
        self.assertEqual(restarted["view"]["status"], "playing")
        self.assertEqual(restarted["view"]["safe_revealed"], 0)

    def test_winning_completes_and_marks_daily_flag(self):
        payload = self._start()
        mines = self._mines(payload["run_id"])
        safe_cells = [index for index in range(81) if index not in mines]
        elapsed = 0
        status = "playing"
        response = None
        for cell in safe_cells:
            elapsed += 1
            response = self._save(payload, cell, elapsed=elapsed)
            if response.status_code == 400 and response.json.get("code") == "CELL_REVEALED":
                continue
            self.assertEqual(response.status_code, 200, response.json)
            status = response.json["status"]
            if status == "won":
                break
        self.assertEqual(status, "won")
        result = response.json["result"]
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["stars"], 1)

        submitted = self.client.post(
            "/api/games/minesweeper/submit",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "elapsed_seconds": elapsed,
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.json)
        self.assertTrue(submitted.json["correct"])
        repeated = self.client.post(
            "/api/games/minesweeper/submit",
            headers=self.auth,
            json={
                "puzzle_id": payload["puzzle_id"],
                "run_id": payload["run_id"],
                "elapsed_seconds": elapsed + 99,
            },
        )
        self.assertEqual(repeated.json, submitted.json)

        overview = self.client.get("/api/games/overview", headers=self.auth).json
        entry = next(item for item in overview["games"] if item["key"] == "minesweeper")
        self.assertTrue(entry["daily_completed"])
        self.assertEqual(entry["progress_percent"], 100)

    def test_practice_difficulties_and_seed(self):
        first = self._start("mode=practice&difficulty=hard")
        self.assertEqual(first["rows"], 16)
        self.assertEqual(first["mines"], 40)
        again = minesweeper._generate_mines(first["puzzle_id"], 16, 16, 40)
        self.assertEqual(len(set(again)), 40)

    def test_invalid_cell_and_action(self):
        payload = self._start()
        bad_cell = self._save(payload, 999)
        self.assertEqual(bad_cell.status_code, 400)
        bad_action = self._save(payload, 0, action="dig")
        self.assertEqual(bad_action.status_code, 400)
        self.assertEqual(bad_action.json["code"], "INVALID_ACTION")


if __name__ == "__main__":
    unittest.main()
