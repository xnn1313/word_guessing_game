import os
import tempfile
import unittest

from flask import Flask, request

import puzzle_api
import puzzle_content
import puzzle_games
import storage


class PuzzleApiTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("api-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "api-tester"}

        app = Flask(__name__)
        app.secret_key = "puzzle-api-test-secret"
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

    def test_seed_catalog_counts(self):
        with storage._connect() as connection:
            counts = dict(
                connection.execute(
                    "SELECT difficulty, COUNT(*) FROM sudoku_puzzles GROUP BY difficulty"
                ).fetchall()
            )
            idiom_count = connection.execute("SELECT COUNT(*) FROM idiom_puzzles").fetchone()[0]
            sudoku_rows = connection.execute(
                "SELECT puzzle, solution FROM sudoku_puzzles"
            ).fetchall()
        self.assertEqual(counts, {"easy": 100, "medium": 100, "hard": 100})
        self.assertEqual(idiom_count, 60)
        self.assertTrue(
            all(puzzle_content.sudoku_solution_valid(row["puzzle"], row["solution"]) for row in sudoku_rows)
        )

    def test_guest_overview_and_cloud_save_authentication(self):
        overview = self.client.get("/api/games/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual([item["key"] for item in overview.json["games"]], ["word", "sudoku", "idiom", "memory"])
        response = self.client.post("/api/sudoku/save", json={})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "AUTH_REQUIRED")
        expired = self.client.get(
            "/api/games/overview", headers={"Authorization": "Bearer expired-token"}
        )
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(expired.json["code"], "INVALID_TOKEN")

    def test_sudoku_daily_save_hint_submit_and_idempotency(self):
        guest = self.client.get("/api/sudoku/puzzle?mode=daily&difficulty=medium")
        self.assertEqual(guest.status_code, 200)
        self.assertIsNone(guest.json["run_id"])
        self.assertIsNone(guest.json["saved_state"])
        self.assertNotIn("solution", guest.get_data(as_text=True))

        response = self.client.get(
            "/api/sudoku/puzzle?mode=daily&difficulty=medium", headers=self.auth
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json
        puzzle = storage.get_sudoku_puzzle(payload["puzzle_id"])
        run_id = payload["run_id"]

        hint = self.client.post(
            "/api/sudoku/hint",
            headers=self.auth,
            json={"run_id": run_id, "puzzle_id": payload["puzzle_id"], "grid": payload["givens"]},
        )
        self.assertEqual(hint.status_code, 200)
        self.assertEqual(hint.json["hints_used"], 1)

        restored = self.client.get(
            "/api/sudoku/puzzle?mode=daily&difficulty=medium", headers=self.auth
        ).json
        self.assertEqual(restored["saved_state"]["hints_used"], 1)
        self.assertEqual(
            restored["saved_state"]["grid"][hint.json["index"]], str(hint.json["value"])
        )

        incorrect_index = next(
            index for index, given in enumerate(payload["givens"]) if given == "0"
        )
        incorrect_grid = (
            puzzle["solution"][:incorrect_index]
            + "0"
            + puzzle["solution"][incorrect_index + 1 :]
        )
        incorrect = self.client.post(
            "/api/sudoku/submit",
            headers=self.auth,
            json={
                "run_id": run_id,
                "puzzle_id": payload["puzzle_id"],
                "grid": incorrect_grid,
                "elapsed_seconds": 120,
                "mistakes": 0,
            },
        )
        self.assertEqual(incorrect.status_code, 422)
        self.assertIn(incorrect_index, incorrect.json["invalid_cells"])
        self.assertNotIn(puzzle["solution"], incorrect.get_data(as_text=True))

        complete_body = {
            "run_id": run_id,
            "puzzle_id": payload["puzzle_id"],
            "grid": puzzle["solution"],
            "elapsed_seconds": 180,
            "mistakes": 1,
        }
        completed = self.client.post("/api/sudoku/submit", headers=self.auth, json=complete_body)
        repeated = self.client.post(
            "/api/sudoku/submit",
            headers=self.auth,
            json={**complete_body, "elapsed_seconds": 9999, "mistakes": 99},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(repeated.json, completed.json)

    def test_sudoku_and_idiom_allow_erasing_non_fixed_cells(self):
        sudoku = self.client.get(
            "/api/sudoku/puzzle?mode=practice&difficulty=easy", headers=self.auth
        ).json
        sudoku_puzzle = storage.get_sudoku_puzzle(sudoku["puzzle_id"])
        editable = next(index for index, value in enumerate(sudoku["givens"]) if value == "0")
        filled_grid = (
            sudoku["givens"][:editable]
            + sudoku_puzzle["solution"][editable]
            + sudoku["givens"][editable + 1 :]
        )
        first_save = self.client.post(
            "/api/sudoku/save",
            headers=self.auth,
            json={
                "run_id": sudoku["run_id"],
                "puzzle_id": sudoku["puzzle_id"],
                "grid": filled_grid,
                "notes": {},
                "elapsed_seconds": 10,
                "mistakes": 0,
            },
        )
        erased_save = self.client.post(
            "/api/sudoku/save",
            headers=self.auth,
            json={
                "run_id": sudoku["run_id"],
                "puzzle_id": sudoku["puzzle_id"],
                "grid": sudoku["givens"],
                "notes": {},
                "elapsed_seconds": 11,
                "mistakes": 0,
            },
        )
        self.assertEqual(first_save.status_code, 200)
        self.assertEqual(erased_save.status_code, 200)

        idiom = self.client.get(
            "/api/idiom/puzzle?mode=level&level_id=idiom-001", headers=self.auth
        ).json
        idiom_puzzle = storage.get_idiom_puzzle(idiom["puzzle_id"])
        solution = puzzle_games._idiom_solution_list(idiom_puzzle)
        editable = next(
            index for index, cell in enumerate(idiom["cells"]) if cell["type"] == "input"
        )
        filled = list(idiom["saved_state"]["grid"])
        filled[editable] = solution[editable]
        first_save = self.client.post(
            "/api/idiom/save",
            headers=self.auth,
            json={
                "run_id": idiom["run_id"],
                "puzzle_id": idiom["puzzle_id"],
                "grid": filled,
                "elapsed_seconds": 10,
                "mistakes": 0,
            },
        )
        filled[editable] = ""
        erased_save = self.client.post(
            "/api/idiom/save",
            headers=self.auth,
            json={
                "run_id": idiom["run_id"],
                "puzzle_id": idiom["puzzle_id"],
                "grid": filled,
                "elapsed_seconds": 11,
                "mistakes": 0,
            },
        )
        self.assertEqual(first_save.status_code, 200)
        self.assertEqual(erased_save.status_code, 200)

    def test_idiom_unlock_save_and_submit(self):
        guest_catalog = self.client.get("/api/idiom/catalog").json
        for category in guest_catalog["categories"]:
            self.assertTrue(category["levels"][0]["unlocked"])
            self.assertFalse(category["levels"][1]["unlocked"])

        guest_second = self.client.get(
            f"/api/idiom/puzzle?mode=level&level_id={guest_catalog['categories'][0]['levels'][1]['id']}"
        )
        self.assertEqual(guest_second.status_code, 200)
        self.assertIsNone(guest_second.json["run_id"])

        first = guest_catalog["categories"][0]["levels"][0]
        second = guest_catalog["categories"][0]["levels"][1]
        locked = self.client.get(
            f"/api/idiom/puzzle?mode=level&level_id={second['id']}", headers=self.auth
        )
        self.assertEqual(locked.status_code, 403)
        self.assertEqual(locked.json["code"], "LEVEL_LOCKED")

        response = self.client.get(
            f"/api/idiom/puzzle?mode=level&level_id={first['id']}", headers=self.auth
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json
        self.assertNotIn("solution", payload)
        puzzle = storage.get_idiom_puzzle(payload["puzzle_id"])
        solution = puzzle_games._idiom_solution_list(puzzle)

        save = self.client.post(
            "/api/idiom/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "puzzle_id": payload["puzzle_id"],
                "grid": payload["saved_state"]["grid"],
                "elapsed_seconds": 10,
                "mistakes": 0,
            },
        )
        self.assertEqual(save.status_code, 200)

        body = {
            "run_id": payload["run_id"],
            "puzzle_id": payload["puzzle_id"],
            "grid": solution,
            "elapsed_seconds": 90,
            "mistakes": 0,
        }
        completed = self.client.post("/api/idiom/submit", headers=self.auth, json=body)
        repeated = self.client.post("/api/idiom/submit", headers=self.auth, json=body)
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(repeated.json, completed.json)
        self.assertEqual(completed.json["result"]["total_stars"], 3)
        catalog = self.client.get("/api/idiom/catalog", headers=self.auth).json
        self.assertTrue(catalog["categories"][0]["levels"][1]["unlocked"])

    def test_memory_daily_save_resume_submit_and_idempotency(self):
        first_guest = self.client.get(
            "/api/memory/board?mode=daily&difficulty=easy&theme=fruit"
        ).json
        second_guest = self.app.test_client().get(
            "/api/memory/board?mode=daily&difficulty=easy&theme=fruit"
        ).json
        self.assertEqual(first_guest["board_id"], second_guest["board_id"])
        self.assertEqual(first_guest["cards"], second_guest["cards"])

        response = self.client.get(
            "/api/memory/board?mode=practice&difficulty=easy&theme=fruit",
            headers=self.auth,
        )
        payload = response.json
        positions_by_face = {}
        for card in payload["cards"]:
            positions_by_face.setdefault(card["face_key"], []).append(card["position"])
        first_pair = next(iter(positions_by_face.values()))

        invalid = self.client.post(
            "/api/memory/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "board_id": payload["board_id"],
                "matched_positions": [first_pair[0]],
                "moves": 1,
                "elapsed_seconds": 5,
            },
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json["code"], "INVALID_MATCHES")

        saved = self.client.post(
            "/api/memory/save",
            headers=self.auth,
            json={
                "run_id": payload["run_id"],
                "board_id": payload["board_id"],
                "matched_positions": first_pair,
                "moves": 1,
                "elapsed_seconds": 5,
            },
        )
        self.assertEqual(saved.status_code, 200)
        restored = self.client.get(
            "/api/memory/board?mode=practice&difficulty=easy&theme=fruit",
            headers=self.auth,
        ).json
        self.assertEqual(restored["board_id"], payload["board_id"])
        self.assertEqual(restored["saved_state"]["matched_positions"], sorted(first_pair))

        complete_body = {
            "run_id": payload["run_id"],
            "board_id": payload["board_id"],
            "matched_positions": list(range(len(payload["cards"]))),
            "moves": 9,
            "elapsed_seconds": 40,
        }
        completed = self.client.post("/api/memory/submit", headers=self.auth, json=complete_body)
        repeated = self.client.post(
            "/api/memory/submit",
            headers=self.auth,
            json={**complete_body, "moves": 100, "elapsed_seconds": 999},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(repeated.json, completed.json)

        overview = self.client.get("/api/games/overview", headers=self.auth).json
        self.assertEqual(overview["summary"]["available_games"], 4)
        self.assertGreaterEqual(overview["summary"]["total_stars"], 3)


if __name__ == "__main__":
    unittest.main()
