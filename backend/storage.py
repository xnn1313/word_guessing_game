import json
import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone


DB_PATH = os.environ.get(
    "WORD_GAME_DB_PATH",
    os.path.join(os.path.dirname(__file__), "word_guessing_game.db"),
)


def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with _connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                game_state TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS campaign_progress (
                user_id INTEGER NOT NULL,
                level_id TEXT NOT NULL,
                stars INTEGER NOT NULL DEFAULT 0,
                best_attempts INTEGER,
                completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, level_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS battle_target_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target_word TEXT NOT NULL,
                played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_battle_target_history_user_word
            ON battle_target_history (user_id, target_word, id DESC)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_api_tokens_user
            ON api_tokens (user_id, expires_at)
            """
        )


def create_user(username, password_hash):
    try:
        with _connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username):
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id):
    with _connect() as connection:
        row = connection.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def _token_hash(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def issue_api_token(user_id, lifetime_days=30):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=lifetime_days)
    with _connect() as connection:
        connection.execute("DELETE FROM api_tokens WHERE expires_at <= CURRENT_TIMESTAMP")
        connection.execute(
            """
            INSERT INTO api_tokens (token_hash, user_id, expires_at)
            VALUES (?, ?, ?)
            """,
            (
                _token_hash(token),
                user_id,
                expires_at.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
    return token


def get_user_by_api_token(token):
    if not token:
        return None
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT users.id, users.username
            FROM api_tokens
            JOIN users ON users.id = api_tokens.user_id
            WHERE api_tokens.token_hash = ?
              AND api_tokens.expires_at > CURRENT_TIMESTAMP
            """,
            (_token_hash(token),),
        ).fetchone()
    return dict(row) if row else None


def revoke_api_token(token):
    if not token:
        return
    with _connect() as connection:
        connection.execute(
            "DELETE FROM api_tokens WHERE token_hash = ?",
            (_token_hash(token),),
        )


def save_game(user_id, game_state):
    serialized = json.dumps(game_state, ensure_ascii=False, separators=(",", ":"))
    with _connect() as connection:
        connection.execute(
            """
            UPDATE users
            SET game_state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (serialized, user_id),
        )


def load_game(user_id):
    with _connect() as connection:
        row = connection.execute(
            "SELECT game_state FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row or not row["game_state"]:
        return None
    try:
        return json.loads(row["game_state"])
    except (TypeError, json.JSONDecodeError):
        return None


def get_campaign_progress(user_id):
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT level_id, stars, best_attempts
            FROM campaign_progress
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
    return {
        row["level_id"]: {
            "stars": row["stars"],
            "best_attempts": row["best_attempts"],
        }
        for row in rows
    }


def save_campaign_result(user_id, level_id, stars, attempts):
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO campaign_progress (user_id, level_id, stars, best_attempts)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, level_id) DO UPDATE SET
                stars = MAX(campaign_progress.stars, excluded.stars),
                best_attempts = CASE
                    WHEN campaign_progress.best_attempts IS NULL THEN excluded.best_attempts
                    ELSE MIN(campaign_progress.best_attempts, excluded.best_attempts)
                END,
                completed_at = CURRENT_TIMESTAMP
            """,
            (user_id, level_id, stars, attempts),
        )


def get_battle_target_last_seen(user_ids):
    """Return each target's latest history row across the supplied players."""
    normalized_ids = sorted({int(user_id) for user_id in user_ids})
    if not normalized_ids:
        return {}

    placeholders = ",".join("?" for _ in normalized_ids)
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT target_word, MAX(id) AS last_seen_id
            FROM battle_target_history
            WHERE user_id IN ({placeholders})
            GROUP BY target_word
            """,
            normalized_ids,
        ).fetchall()
    return {row["target_word"]: row["last_seen_id"] for row in rows}


def record_battle_target(user_ids, target_word):
    """Persist one target exposure for every player in a battle round."""
    normalized_ids = sorted({int(user_id) for user_id in user_ids})
    if not normalized_ids:
        return

    with _connect() as connection:
        connection.executemany(
            """
            INSERT INTO battle_target_history (user_id, target_word)
            VALUES (?, ?)
            """,
            [(user_id, target_word) for user_id in normalized_ids],
        )
