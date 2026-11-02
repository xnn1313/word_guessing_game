"""Tests for the uniform API error envelope."""

import unittest

from flask import Flask, jsonify

from core.errors import install_error_handlers


class ErrorEnvelopeTestCase(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.testing = True
        install_error_handlers(app)

        @app.get("/api/bare")
        def bare():
            return jsonify({"error": "出错了"}), 401

        @app.get("/api/coded")
        def coded():
            return jsonify({"error": "已失效", "code": "INVALID_TOKEN"}), 401

        @app.get("/api/ok")
        def ok():
            return jsonify({"items": []})

        @app.get("/page")
        def page():
            return "html"

        self.client = app.test_client()

    def test_missing_code_is_derived_from_status(self):
        response = self.client.get("/api/bare")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "出错了", "code": "UNAUTHORIZED"})

    def test_existing_code_is_kept(self):
        response = self.client.get("/api/coded")
        self.assertEqual(response.json["code"], "INVALID_TOKEN")

    def test_success_payload_is_untouched(self):
        response = self.client.get("/api/ok")
        self.assertEqual(response.json, {"items": []})
        self.assertNotIn("code", response.json)

    def test_api_404_is_json(self):
        response = self.client.get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json["code"], "NOT_FOUND")

    def test_method_not_allowed(self):
        response = self.client.post("/api/ok")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json["code"], "METHOD_NOT_ALLOWED")

    def test_non_api_pages_stay_html(self):
        response = self.client.get("/missing-page")
        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(response.mimetype, "application/json")

    def test_unhandled_api_error_is_json_500(self):
        app = Flask(__name__)
        app.testing = False
        app.debug = False
        install_error_handlers(app)

        @app.get("/api/boom")
        def boom():
            raise ValueError("boom")

        response = app.test_client().get("/api/boom")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["code"], "INTERNAL_ERROR")


if __name__ == "__main__":
    unittest.main()
