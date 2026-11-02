"""Contract tests for the game plugin registry.

These tests walk ``REGISTRY`` instead of naming each game, so a new plugin is
covered the moment it is registered.  They are the safety net that keeps the
"add one module, not seven call sites" promise honest.
"""

import os
import tempfile
import unittest

from flask import Flask, request

import puzzle_api
import puzzle_games
import storage
from games import REGISTRY
from routes.games import LEGACY_ROUTES


class GameRegistryContractTestCase(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        os.unlink(self.db_path)
        self.original_db_path = storage.DB_PATH
        storage.DB_PATH = self.db_path
        storage.init_db()
        self.user_id = storage.create_user("registry-tester", "unused-password-hash")
        self.user = {"id": self.user_id, "username": "registry-tester"}

        app = Flask(__name__)
        app.secret_key = "games-registry-test-secret"
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

    def test_specs_are_consistent(self):
        self.assertTrue(REGISTRY)
        for key, spec in REGISTRY.items():
            with self.subTest(game=key):
                self.assertEqual(key, spec.key)
                self.assertTrue(spec.title)
                self.assertIsNotNone(spec.start, "a game must be startable")
                self.assertIn(spec.status, ("always_200", "422_if_incorrect"))

    def test_overview_is_built_from_the_registry(self):
        payload = self.client.get("/api/games/overview", headers=self.auth).json
        keys = [item["key"] for item in payload["games"]]
        self.assertEqual(keys, ["word"] + [spec.key for spec in sorted(REGISTRY.values(), key=lambda s: (s.order, s.key))])
        self.assertEqual(payload["summary"]["available_games"], 1 + len(REGISTRY))
        self.assertEqual(
            payload["summary"]["daily_total"],
            len([spec for spec in REGISTRY.values() if spec.daily]),
        )
        titles = {item["key"]: item["title"] for item in payload["games"]}
        for spec in REGISTRY.values():
            self.assertEqual(titles[spec.key], spec.title)

    def test_every_game_starts_through_the_generic_route(self):
        for spec in REGISTRY.values():
            with self.subTest(game=spec.key):
                response = self.client.get(
                    f"/api/games/{spec.key}/start?mode=daily&difficulty=easy",
                    headers=self.auth,
                )
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertTrue(
                    "puzzle_id" in response.json or "board_id" in response.json
                )

    def test_legacy_aliases_still_resolve(self):
        for path, _key, action, methods in LEGACY_ROUTES:
            with self.subTest(path=path):
                if "GET" in methods:
                    query = "?mode=daily&difficulty=easy" if action == "start" else ""
                    response = self.client.get(path + query, headers=self.auth)
                    self.assertEqual(response.status_code, 200, response.get_json())
                else:
                    response = self.client.post(path, headers=self.auth)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json["code"], "INVALID_JSON")

    def test_unknown_game_and_action_are_json_404(self):
        response = self.client.get("/api/games/nope/start")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["code"], "NOT_FOUND")

    def test_invalid_bearer_token_is_401(self):
        response = self.client.get(
            "/api/games/overview", headers={"Authorization": "Bearer expired"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["code"], "INVALID_TOKEN")


if __name__ == "__main__":
    unittest.main()
