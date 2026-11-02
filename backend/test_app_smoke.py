"""Smoke tests for the real ``app`` module.

The BGE model is stubbed so these tests can run without torch/model weights;
everything else (sessions, auth, rate limiting, error envelopes, battle rooms)
is the production wiring.  They exist because the session/limit/error-handler
refactor touched code paths the puzzle tests never reach.
"""

import logging
import logging.handlers
import os
import sys
import tempfile
import types
import unittest
import uuid

_TMP = tempfile.mkdtemp(prefix="word-game-smoke-")
os.environ["WORD_GAME_DB_PATH"] = os.path.join(_TMP, "smoke.db")
os.environ.setdefault("WORD_GAME_SECRET_KEY", "smoke-test-secret")
os.environ.pop("WORD_GAME_ENV", None)

# Keep test traffic out of the production app.log.
logging.handlers.RotatingFileHandler = lambda *args, **kwargs: logging.NullHandler()

_fake_similarity = types.ModuleType("similarity")
_fake_similarity.get_model = lambda: None
_fake_similarity.compute_similarity = lambda word, target: 100.0 if word == target else 50.0
sys.modules["similarity"] = _fake_similarity

import app as app_module  # noqa: E402


class AppSmokeTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def _register(self):
        username = f"smoke{uuid.uuid4().hex[:8]}"
        response = self.client.post(
            "/api/mobile/auth/register",
            json={"username": username, "password": "smoke-pass-123"},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return username, response.json["token"], {"Authorization": f"Bearer {response.json['token']}"}

    def test_mobile_register_and_status(self):
        username, _token, auth = self._register()
        response = self.client.get("/api/auth/status", headers=auth)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["authenticated"])
        self.assertEqual(response.json["username"], username)
        self.assertIn("game", response.json)

    def test_guest_classic_guess_flow(self):
        start = self.client.post("/api/classic/start")
        self.assertEqual(start.status_code, 200, start.get_json())
        session_id = start.json["game"]["session_id"]
        guess = self.client.post(
            "/api/guess", json={"word": "苹果", "session_id": session_id}
        )
        self.assertEqual(guess.status_code, 200, guess.get_json())
        self.assertEqual(len(guess.json["history"]), 1)

    def test_battle_room_lifecycle(self):
        _username, _token, auth = self._register()
        created = self.client.post("/api/battle/create", headers=auth)
        self.assertEqual(created.status_code, 201, created.get_json())
        code = created.json["code"]
        self.assertEqual(len(code), 6)
        current = self.client.get("/api/battle/current", headers=auth)
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json["code"], code)
        left = self.client.post("/api/battle/leave", headers=auth)
        self.assertEqual(left.status_code, 200)
        after = self.client.get("/api/battle/current", headers=auth)
        self.assertEqual(after.status_code, 404)

    def test_login_limiter_blocks_after_repeated_failures(self):
        username = f"limit{uuid.uuid4().hex[:8]}"
        self.client.post(
            "/api/mobile/auth/register",
            json={"username": username, "password": "right-pass-123"},
        )
        for _ in range(8):
            response = self.client.post(
                "/api/mobile/auth/login",
                json={"username": username, "password": "wrong-pass-123"},
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            "/api/mobile/auth/login",
            json={"username": username, "password": "right-pass-123"},
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json["code"], "TOO_MANY_REQUESTS")

    def test_unknown_api_path_uses_json_envelope(self):
        response = self.client.get("/api/definitely-missing")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["code"], "NOT_FOUND")

    def test_web_login_sets_cookie(self):
        username = f"web{uuid.uuid4().hex[:8]}"
        self.client.post(
            "/api/auth/register",
            json={"username": username, "password": "web-pass-123"},
        )
        login = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": "web-pass-123"},
        )
        self.assertEqual(login.status_code, 200, login.get_json())
        status = self.client.get("/api/auth/status")
        self.assertTrue(status.json["authenticated"])


if __name__ == "__main__":
    unittest.main()
