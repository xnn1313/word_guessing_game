import json
import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone


DB_PATH = os.environ.get(
    "WORD_GAME_DB_PATH",
    os.path.join(os.path.dirname(__file__), "word_guessing_game.db"),
)


@contextmanager
def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS game_runs (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                game_key TEXT NOT NULL,
                puzzle_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                difficulty TEXT,
                status TEXT NOT NULL DEFAULT 'playing',
                state_json TEXT,
                elapsed_seconds INTEGER NOT NULL DEFAULT 0,
                hints_used INTEGER NOT NULL DEFAULT 0,
                mistakes INTEGER NOT NULL DEFAULT 0,
                score INTEGER,
                stars INTEGER,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_game_runs_user_game
            ON game_runs (user_id, game_key, updated_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_game_runs_user_puzzle
            ON game_runs (user_id, game_key, puzzle_id, status)
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_game_runs_one_playing
            ON game_runs (user_id, game_key, puzzle_id)
            WHERE status = 'playing'
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sudoku_puzzles (
                id TEXT PRIMARY KEY,
                difficulty TEXT NOT NULL,
                puzzle TEXT NOT NULL,
                solution TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sudoku_difficulty
            ON sudoku_puzzles (difficulty, is_active)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS idiom_puzzles (
                id TEXT PRIMARY KEY,
                level_order INTEGER,
                category TEXT,
                difficulty TEXT NOT NULL,
                title TEXT NOT NULL,
                size INTEGER NOT NULL,
                layout_json TEXT NOT NULL,
                clues_json TEXT NOT NULL,
                solution_json TEXT NOT NULL,
                layout_version INTEGER NOT NULL DEFAULT 1,
                is_daily_enabled INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        idiom_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(idiom_puzzles)").fetchall()
        }
        if "layout_version" not in idiom_columns:
            connection.execute(
                "ALTER TABLE idiom_puzzles ADD COLUMN layout_version INTEGER NOT NULL DEFAULT 1"
            )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_idiom_level_order
            ON idiom_puzzles (level_order)
            WHERE level_order IS NOT NULL
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_puzzles (
                game_key TEXT NOT NULL,
                puzzle_date TEXT NOT NULL,
                difficulty TEXT NOT NULL DEFAULT 'medium',
                puzzle_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (game_key, puzzle_date, difficulty)
            )
            """
        )

        # Seeded content is deterministic and idempotent. Puzzle generation and
        # uniqueness checks happen here, never in an HTTP request path.
        from puzzle_content import seed_puzzle_catalogs

        seed_puzzle_catalogs(connection)


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


def utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _deserialize_run(row):
    if not row:
        return None
    result = dict(row)
    try:
        result["state"] = json.loads(result.pop("state_json") or "{}")
    except (TypeError, json.JSONDecodeError):
        result["state"] = {}
        result.pop("state_json", None)
    return result


def create_game_run(user_id, game_key, puzzle_id, mode, difficulty, state):
    existing = get_playing_run(user_id, game_key, puzzle_id)
    if existing:
        return existing
    run_id = f"run_{secrets.token_hex(8)}"
    now = utc_now_iso()
    serialized = json.dumps(state or {}, ensure_ascii=False, separators=(",", ":"))
    try:
        with _connect() as connection:
            connection.execute(
                """
                INSERT INTO game_runs (
                    id, user_id, game_key, puzzle_id, mode, difficulty,
                    state_json, started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, user_id, game_key, puzzle_id, mode, difficulty, serialized, now, now),
            )
    except sqlite3.IntegrityError:
        return get_playing_run(user_id, game_key, puzzle_id)
    return get_game_run(run_id)


def get_game_run(run_id):
    if not run_id:
        return None
    with _connect() as connection:
        row = connection.execute("SELECT * FROM game_runs WHERE id = ?", (run_id,)).fetchone()
    return _deserialize_run(row)


def get_playing_run(user_id, game_key, puzzle_id):
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM game_runs
            WHERE user_id = ? AND game_key = ? AND puzzle_id = ? AND status = 'playing'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (user_id, game_key, puzzle_id),
        ).fetchone()
    return _deserialize_run(row)


def get_latest_playing_run(user_id, game_key, mode, difficulty=None):
    params = [user_id, game_key, mode]
    difficulty_sql = ""
    if difficulty is not None:
        difficulty_sql = " AND difficulty = ?"
        params.append(difficulty)
    with _connect() as connection:
        row = connection.execute(
            f"""
            SELECT * FROM game_runs
            WHERE user_id = ? AND game_key = ? AND mode = ? AND status = 'playing'
            {difficulty_sql}
            ORDER BY updated_at DESC, rowid DESC LIMIT 1
            """,
            params,
        ).fetchone()
    return _deserialize_run(row)


def get_latest_memory_playing_run(user_id, mode, difficulty, theme):
    """Return the newest unfinished memory run for one exact board theme."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM game_runs
            WHERE user_id = ? AND game_key = 'memory' AND mode = ?
              AND difficulty = ? AND status = 'playing'
            ORDER BY updated_at DESC, rowid DESC
            """,
            (user_id, mode, difficulty),
        ).fetchall()
    for row in rows:
        run = _deserialize_run(row)
        if run["state"].get("theme") == theme:
            return run
    return None


def get_latest_word_search_playing_run(user_id, mode, difficulty, theme):
    """Return the newest unfinished word-search run for one exact theme."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM game_runs
            WHERE user_id = ? AND game_key = 'word_search' AND mode = ?
              AND difficulty = ? AND status = 'playing'
            ORDER BY updated_at DESC, rowid DESC
            """,
            (user_id, mode, difficulty),
        ).fetchall()
    for row in rows:
        run = _deserialize_run(row)
        if run["state"].get("theme") == theme:
            return run
    return None


def abandon_word_search_playing_runs(user_id, mode, difficulty, theme):
    """Close unfinished word-search runs superseded by an explicit fresh board."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, state_json FROM game_runs
            WHERE user_id = ? AND game_key = 'word_search' AND mode = ?
              AND difficulty = ? AND status = 'playing'
            """,
            (user_id, mode, difficulty),
        ).fetchall()
        run_ids = []
        for row in rows:
            try:
                state = json.loads(row["state_json"] or "{}")
            except (TypeError, ValueError):
                state = {}
            if state.get("theme") == theme:
                run_ids.append(row["id"])
        if run_ids:
            timestamp = utc_now_iso()
            connection.executemany(
                """
                UPDATE game_runs
                SET status = 'abandoned', updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'playing'
                """,
                [(timestamp, run_id, user_id) for run_id in run_ids],
            )
    return len(run_ids)


def abandon_memory_playing_runs(user_id, mode, difficulty, theme):
    """Close unfinished runs superseded by an explicit fresh memory board."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, state_json FROM game_runs
            WHERE user_id = ? AND game_key = 'memory' AND mode = ?
              AND difficulty = ? AND status = 'playing'
            """,
            (user_id, mode, difficulty),
        ).fetchall()
        run_ids = []
        for row in rows:
            try:
                state = json.loads(row["state_json"] or "{}")
            except (TypeError, ValueError):
                state = {}
            if state.get("theme") == theme:
                run_ids.append(row["id"])
        if run_ids:
            timestamp = utc_now_iso()
            connection.executemany(
                """
                UPDATE game_runs
                SET status = 'abandoned', updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'playing'
                """,
                [(timestamp, run_id, user_id) for run_id in run_ids],
            )
    return len(run_ids)


def update_game_run(run_id, user_id, state, elapsed_seconds, hints_used, mistakes):
    now = utc_now_iso()
    serialized = json.dumps(state or {}, ensure_ascii=False, separators=(",", ":"))
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE game_runs
            SET state_json = ?, elapsed_seconds = ?, hints_used = ?, mistakes = ?, updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'playing'
            """,
            (serialized, elapsed_seconds, hints_used, mistakes, now, run_id, user_id),
        )
        updated = cursor.rowcount > 0
    return updated, now


def complete_game_run(run_id, user_id, state, elapsed_seconds, hints_used, mistakes, score, stars):
    now = utc_now_iso()
    serialized = json.dumps(state or {}, ensure_ascii=False, separators=(",", ":"))
    with _connect() as connection:
        cursor = connection.execute(
            """
            UPDATE game_runs
            SET status = 'completed', state_json = ?, elapsed_seconds = ?, hints_used = ?,
                mistakes = ?, score = ?, stars = ?, updated_at = ?, completed_at = ?
            WHERE id = ? AND user_id = ? AND status = 'playing'
            """,
            (serialized, elapsed_seconds, hints_used, mistakes, score, stars, now, now, run_id, user_id),
        )
        completed = cursor.rowcount > 0
    return completed, get_game_run(run_id)


def get_recent_completed_puzzle_ids(user_id, game_key, difficulty=None, limit=20):
    params = [user_id, game_key]
    difficulty_sql = ""
    if difficulty is not None:
        difficulty_sql = " AND difficulty = ?"
        params.append(difficulty)
    params.append(max(1, min(int(limit), 100)))
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT puzzle_id FROM game_runs
            WHERE user_id = ? AND game_key = ? AND status = 'completed'
            {difficulty_sql}
            ORDER BY completed_at DESC LIMIT ?
            """,
            params,
        ).fetchall()
    return [row["puzzle_id"] for row in rows]


def get_sudoku_puzzle(puzzle_id):
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM sudoku_puzzles WHERE id = ? AND is_active = 1",
            (puzzle_id,),
        ).fetchone()
    return dict(row) if row else None


def list_sudoku_puzzle_ids(difficulty):
    with _connect() as connection:
        rows = connection.execute(
            "SELECT id FROM sudoku_puzzles WHERE difficulty = ? AND is_active = 1 ORDER BY id",
            (difficulty,),
        ).fetchall()
    return [row["id"] for row in rows]


def get_idiom_puzzle(puzzle_id):
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM idiom_puzzles WHERE id = ? AND is_active = 1",
            (puzzle_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    for key in ("layout_json", "clues_json", "solution_json"):
        try:
            result[key[:-5]] = json.loads(result[key])
        except (TypeError, json.JSONDecodeError):
            result[key[:-5]] = [] if key != "solution_json" else {}
    return result


def list_idiom_puzzles(daily_only=False):
    daily_sql = " AND is_daily_enabled = 1" if daily_only else ""
    with _connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, level_order, category, difficulty, title
            FROM idiom_puzzles
            WHERE is_active = 1 {daily_sql}
            ORDER BY level_order, id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_daily_puzzle_id(game_key, puzzle_date, difficulty):
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT puzzle_id FROM daily_puzzles
            WHERE game_key = ? AND puzzle_date = ? AND difficulty = ?
            """,
            (game_key, puzzle_date, difficulty),
        ).fetchone()
    return row["puzzle_id"] if row else None


def set_daily_puzzle_id(game_key, puzzle_date, difficulty, puzzle_id):
    with _connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO daily_puzzles (game_key, puzzle_date, difficulty, puzzle_id)
            VALUES (?, ?, ?, ?)
            """,
            (game_key, puzzle_date, difficulty, puzzle_id),
        )
    return get_daily_puzzle_id(game_key, puzzle_date, difficulty)


def get_idiom_progress(user_id):
    if not user_id:
        return {}
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT puzzle_id, MAX(stars) AS stars, MAX(score) AS best_score
            FROM game_runs
            WHERE user_id = ? AND game_key = 'idiom' AND mode = 'level' AND status = 'completed'
            GROUP BY puzzle_id
            """,
            (user_id,),
        ).fetchall()
    return {
        row["puzzle_id"]: {"stars": row["stars"] or 0, "best_score": row["best_score"]}
        for row in rows
    }


def get_level_progress(user_id, game_key):
    """Return best results for deterministic level-mode puzzles."""
    if not user_id:
        return {}
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT puzzle_id, MAX(stars) AS stars, MAX(score) AS best_score
            FROM game_runs
            WHERE user_id = ? AND game_key = ? AND mode = 'level' AND status = 'completed'
            GROUP BY puzzle_id
            """,
            (user_id, game_key),
        ).fetchall()
    return {
        row["puzzle_id"]: {"stars": row["stars"] or 0, "best_score": row["best_score"]}
        for row in rows
    }


def get_game_run_stats(user_id):
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT game_key, MAX(score) AS best_score, MAX(updated_at) AS last_played_at
            FROM game_runs
            WHERE user_id = ?
            GROUP BY game_key
            """,
            (user_id,),
        ).fetchall()
        star_rows = connection.execute(
            """
            SELECT game_key, SUM(best_stars) AS total_stars
            FROM (
                SELECT game_key, puzzle_id, MAX(stars) AS best_stars
                FROM game_runs
                WHERE user_id = ? AND status = 'completed'
                GROUP BY game_key, puzzle_id
            )
            GROUP BY game_key
            """,
            (user_id,),
        ).fetchall()
        memory_rows = connection.execute(
            """
            SELECT state_json FROM game_runs
            WHERE user_id = ? AND game_key = 'memory' AND status = 'completed'
            """,
            (user_id,),
        ).fetchall()
    result = {
        row["game_key"]: {
            "best_score": row["best_score"],
            "last_played_at": row["last_played_at"],
            "total_stars": 0,
        }
        for row in rows
    }
    for row in star_rows:
        result.setdefault(row["game_key"], {"best_score": None, "last_played_at": None})[
            "total_stars"
        ] = row["total_stars"] or 0
    moves = []
    for row in memory_rows:
        try:
            value = json.loads(row["state_json"] or "{}").get("moves")
            if isinstance(value, int):
                moves.append(value)
        except (TypeError, json.JSONDecodeError):
            continue
    if moves:
        result.setdefault("memory", {"best_score": None, "last_played_at": None, "total_stars": 0})[
            "best_moves"
        ] = min(moves)
    return result


def get_daily_completion_flags(user_id, puzzle_date):
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT daily_puzzles.game_key
            FROM daily_puzzles
            JOIN game_runs
              ON game_runs.game_key = daily_puzzles.game_key
             AND game_runs.puzzle_id = daily_puzzles.puzzle_id
            WHERE daily_puzzles.puzzle_date = ?
              AND game_runs.user_id = ?
              AND game_runs.mode = 'daily'
              AND game_runs.status = 'completed'
            GROUP BY daily_puzzles.game_key
            """,
            (puzzle_date, user_id),
        ).fetchall()
    return {row["game_key"] for row in rows}


def get_word_overview(user_id):
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(stars), 0) AS total_stars,
                   MAX(completed_at) AS last_played_at
            FROM campaign_progress WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else {"total_stars": 0, "last_played_at": None}
