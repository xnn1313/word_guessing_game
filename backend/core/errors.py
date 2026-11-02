"""Uniform JSON error envelopes for everything under ``/api/``.

Handlers in this codebase grew up in two eras: the word-game routes return
``{"error": "..."}`` while the puzzle routes return ``{"error": ..., "code":
...}``.  Instead of editing dozens of returns, this module normalises at the
edges:

* framework errors (404/405/…) become JSON for API paths;
* any JSON body that has ``error`` but no ``code`` gets a stable code derived
  from the HTTP status.
"""

from __future__ import annotations

import json

from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
}


def error_code(status: int) -> str:
    return STATUS_CODES.get(status, f"HTTP_{status}")


def install_error_handlers(app):
    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description, "code": error_code(exc.code)}), exc.code
        return exc

    @app.errorhandler(Exception)
    def unhandled_error(exc):
        # Testing/debug modes keep Flask's traceback page; production returns
        # a stable JSON envelope instead of an HTML 500 for API clients.
        if current_app.debug or current_app.testing:
            raise exc
        current_app.logger.exception("未处理的异常: %s %s", request.method, request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "服务器内部错误", "code": "INTERNAL_ERROR"}), 500
        raise exc

    @app.after_request
    def attach_error_code(response):
        if response.is_json:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict) and payload.get("error") and not payload.get("code"):
                payload["code"] = error_code(response.status_code)
                response.set_data(json.dumps(payload, ensure_ascii=False))
                response.content_type = "application/json"
        return response

    return app
