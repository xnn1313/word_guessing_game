import uuid
import logging
import sys
import os
import re
from datetime import timedelta
from flask import Flask, g, request, jsonify, send_from_directory, session as flask_session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import game_manager
import storage
import campaign
import multiplayer
import puzzle_api

# 修复 Windows 下 stdout 中文编码问题
if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "app.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../frontend", static_url_path="")
app.secret_key = os.environ.get("WORD_GAME_SECRET_KEY", "development-only-change-me")
app.permanent_session_lifetime = timedelta(days=30)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
CORS(app, supports_credentials=True)
storage.init_db()

if app.secret_key == "development-only-change-me":
    logger.warning("未配置 WORD_GAME_SECRET_KEY，登录会话不适合生产环境")

# 启动时预加载BGE模型，避免首次请求等待过久
import similarity

similarity.get_model()
logger.info("BGE模型已预加载完成")

sessions = {}
mobile_sessions = {}


def get_current_api_token():
    if hasattr(g, "api_token"):
        return g.api_token
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None
    g.api_token = token or None
    return g.api_token


def get_current_user():
    if hasattr(g, "current_user"):
        return g.current_user

    api_token = get_current_api_token()
    if api_token:
        user = storage.get_user_by_api_token(api_token)
    else:
        user_id = flask_session.get("user_id")
        user = storage.get_user_by_id(user_id) if user_id else None
        if user_id and not user:
            flask_session.clear()
    g.current_user = user
    return g.current_user


puzzle_api.register_puzzle_routes(app, get_current_user)


def create_runtime_game(saved_state=None):
    session_id = str(uuid.uuid4())
    gm = game_manager.GameManager.from_dict(saved_state)
    if gm.mode == "campaign" and gm.campaign_level_id:
        level = campaign.get_level(gm.campaign_level_id)
        if not level or gm.target_word != level["target"]:
            # Content updates may change a level target; restart that level safely.
            if level:
                gm.start_campaign_level(level["id"], level["target"])
            else:
                gm.start_new_round()
    sessions[session_id] = gm
    return session_id, gm


def persist_authenticated_game(gm):
    user = get_current_user()
    if user:
        storage.save_game(user["id"], gm.to_dict())


def auth_game_payload(user, session_id, gm):
    game = gm.get_status()
    game["session_id"] = session_id
    return {
        "authenticated": True,
        "username": user["username"],
        "game": game,
    }


def get_or_create_session():
    user = get_current_user()
    if user:
        api_token = get_current_api_token()
        session_id = mobile_sessions.get(api_token) if api_token else flask_session.get("game_id")
        if not session_id or session_id not in sessions:
            session_id, gm = create_runtime_game(storage.load_game(user["id"]))
            if api_token:
                mobile_sessions[api_token] = session_id
            else:
                flask_session["game_id"] = session_id
            persist_authenticated_game(gm)
            logger.info(f"恢复用户存档: {user['username']}, 会话: {session_id}")
        return session_id, sessions[session_id]

    session_id = request.args.get("session_id") or request.headers.get("X-Session-ID")
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        gm = game_manager.GameManager()
        gm.start_new_round()
        sessions[session_id] = gm
        logger.info(f"创建新会话: {session_id}, 目标词: 「{gm.target_word}」 (活跃会话数: {len(sessions)})")
    return session_id, sessions[session_id]


def validate_credentials(data):
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not 2 <= len(username) <= 24:
        return None, None, "用户名长度需为 2–24 个字符"
    if not re.fullmatch(r"[\w\-\u4e00-\u9fff]+", username):
        return None, None, "用户名只能包含中文、字母、数字、下划线或连字符"
    if not 6 <= len(password) <= 128:
        return None, None, "密码长度需为 6–128 个字符"
    return username, password, None


def mobile_auth_payload(user, saved_state=None):
    token = storage.issue_api_token(user["id"])
    session_id, gm = create_runtime_game(saved_state)
    mobile_sessions[token] = session_id
    payload = auth_game_payload(user, session_id, gm)
    payload.update({"token": token, "expires_in_days": 30})
    return payload


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/auth/status")
def auth_status():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False})
    session_id, gm = get_or_create_session()
    return jsonify(auth_game_payload(user, session_id, gm))


@app.route("/api/mobile/auth/register", methods=["POST"])
def mobile_register():
    data = request.get_json(silent=True) or {}
    username, password, error = validate_credentials(data)
    if error:
        return jsonify({"error": error}), 400

    user_id = storage.create_user(username, generate_password_hash(password))
    if not user_id:
        return jsonify({"error": "用户名已存在"}), 409
    user = {"id": user_id, "username": username}
    payload = mobile_auth_payload(user)
    storage.save_game(user_id, sessions[payload["game"]["session_id"]].to_dict())
    logger.info(f"小程序注册用户: {username}")
    return jsonify(payload), 201


@app.route("/api/mobile/auth/login", methods=["POST"])
def mobile_login():
    data = request.get_json(silent=True) or {}
    username, password, error = validate_credentials(data)
    if error:
        return jsonify({"error": error}), 400

    user_record = storage.get_user_by_username(username)
    if not user_record or not check_password_hash(user_record["password_hash"], password):
        return jsonify({"error": "用户名或密码错误"}), 401
    user = {"id": user_record["id"], "username": user_record["username"]}
    payload = mobile_auth_payload(user, storage.load_game(user_record["id"]))
    logger.info(f"小程序用户登录: {user['username']}")
    return jsonify(payload)


def battle_user_or_error():
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "请先登录后再进入双人竞速"}), 401)
    return user, None


def battle_error_response(error):
    return jsonify({"error": error.message}), error.status_code


@app.route("/api/battle/create", methods=["POST"])
def create_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    try:
        state = multiplayer.create_room(user)
        logger.info(f"创建双人房间: {state['code']}, 房主: {user['username']}")
        return jsonify(state), 201
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/join", methods=["POST"])
def join_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        state = multiplayer.join_room(user, data.get("code"))
        logger.info(f"加入双人房间: {state['code']}, 玩家: {user['username']}")
        return jsonify(state)
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/current")
def current_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    try:
        return jsonify(multiplayer.get_current_room(user["id"]))
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/start", methods=["POST"])
def start_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        state = multiplayer.start_room(user["id"], data.get("code"))
        logger.info(f"开始双人比赛: {state['code']}")
        return jsonify(state)
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/guess", methods=["POST"])
def battle_guess():
    user, error = battle_user_or_error()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        state = multiplayer.make_guess(user["id"], data.get("word"))
        logger.info(
            f"双人猜测 - 房间: {state['code']}, 玩家: {user['username']}, "
            f"相似度: {state['guess_result']['similarity']}%, 猜中: {state['guess_result']['is_correct']}"
        )
        return jsonify(state)
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/leave", methods=["POST"])
def leave_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    try:
        result = multiplayer.leave_room(user["id"])
        logger.info(f"离开双人房间: {result['code']}, 玩家: {user['username']}")
        return jsonify(result)
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/battle/rematch", methods=["POST"])
def rematch_battle_room():
    user, error = battle_user_or_error()
    if error:
        return error
    try:
        state = multiplayer.request_rematch(user["id"])
        logger.info(f"双人再战确认: {state['code']}, 玩家: {user['username']}, 状态: {state['state']}")
        return jsonify(state)
    except multiplayer.BattleError as exc:
        return battle_error_response(exc)


@app.route("/api/campaign")
def campaign_catalog():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录后再进入分类闯关"}), 401
    progress = storage.get_campaign_progress(user["id"])
    return jsonify(campaign.public_catalog(progress))


@app.route("/api/campaign/start", methods=["POST"])
def start_campaign_level():
    user = get_current_user()
    if not user:
        return jsonify({"error": "请先登录后再进入分类闯关"}), 401

    data = request.get_json(silent=True) or {}
    level = campaign.get_level(str(data.get("level_id", "")))
    if not level:
        return jsonify({"error": "关卡不存在"}), 404

    progress = storage.get_campaign_progress(user["id"])
    if not campaign.is_unlocked(level["id"], progress):
        return jsonify({"error": "请先完成上一关"}), 403

    session_id, gm = get_or_create_session()
    gm.start_campaign_level(level["id"], level["target"])
    persist_authenticated_game(gm)
    game = gm.get_status()
    game["session_id"] = session_id
    return jsonify({
        "game": game,
        "level": campaign.public_level(level, progress),
    })


@app.route("/api/classic/start", methods=["POST"])
def start_classic_mode():
    session_id, gm = get_or_create_session()
    if gm.mode != "classic":
        gm.start_new_round()
        persist_authenticated_game(gm)
    game = gm.get_status()
    game["session_id"] = session_id
    return jsonify({"game": game})


@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username, password, error = validate_credentials(data)
    if error:
        return jsonify({"error": error}), 400

    user_id = storage.create_user(username, generate_password_hash(password))
    if not user_id:
        return jsonify({"error": "用户名已存在"}), 409

    flask_session.clear()
    flask_session.permanent = True
    flask_session["user_id"] = user_id
    anonymous_session_id = str(data.get("session_id", ""))
    if anonymous_session_id and anonymous_session_id in sessions:
        session_id = anonymous_session_id
        gm = sessions[session_id]
    else:
        session_id, gm = create_runtime_game()
    flask_session["game_id"] = session_id
    storage.save_game(user_id, gm.to_dict())
    user = {"id": user_id, "username": username}
    logger.info(f"注册用户: {username}")
    return jsonify(auth_game_payload(user, session_id, gm)), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username, password, error = validate_credentials(data)
    if error:
        return jsonify({"error": error}), 400

    user_record = storage.get_user_by_username(username)
    if not user_record or not check_password_hash(user_record["password_hash"], password):
        return jsonify({"error": "用户名或密码错误"}), 401

    flask_session.clear()
    flask_session.permanent = True
    flask_session["user_id"] = user_record["id"]
    session_id, gm = create_runtime_game(storage.load_game(user_record["id"]))
    flask_session["game_id"] = session_id
    user = {"id": user_record["id"], "username": user_record["username"]}
    logger.info(f"用户登录: {user['username']}")
    return jsonify(auth_game_payload(user, session_id, gm))


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    user = get_current_user()
    api_token = get_current_api_token()
    session_id = mobile_sessions.pop(api_token, None) if api_token else flask_session.get("game_id")
    if user:
        try:
            multiplayer.leave_room(user["id"])
        except multiplayer.BattleError:
            pass
    if user and session_id in sessions:
        storage.save_game(user["id"], sessions[session_id].to_dict())
        del sessions[session_id]
    if api_token:
        storage.revoke_api_token(api_token)
    flask_session.clear()
    return jsonify({"message": "已退出登录"})


@app.route("/api/new-game")
def new_game():
    user = get_current_user()
    if user:
        session_id, gm = get_or_create_session()
        gm.reset_full_game()
        persist_authenticated_game(gm)
        return jsonify({"game_id": session_id, "message": "游戏已开始"})

    session_id = request.args.get("session_id") or request.headers.get("X-Session-ID")
    gm = game_manager.GameManager()
    gm.start_new_round()
    new_id = str(uuid.uuid4())
    sessions[new_id] = gm
    if session_id and session_id in sessions:
        del sessions[session_id]
    logger.info(f"新游戏: {new_id}, 目标词: 「{gm.target_word}」")
    return jsonify({"game_id": new_id, "message": "游戏已开始"})


@app.route("/api/guess", methods=["POST"])
def guess():
    session_id, gm = get_or_create_session()
    data = request.get_json()
    if not data or "word" not in data:
        return jsonify({"error": "请提供猜测词"}), 400
    word = data["word"].strip()
    if not word:
        return jsonify({"error": "猜测词不能为空"}), 400

    mode = gm.mode
    campaign_level_id = gm.campaign_level_id
    result = gm.make_guess(word)

    if mode == "campaign" and result.get("is_correct"):
        user = get_current_user()
        if not user:
            return jsonify({"error": "登录状态已失效，请重新登录"}), 401
        stars = campaign.calculate_stars(result["attempts"])
        storage.save_campaign_result(user["id"], campaign_level_id, stars, result["attempts"])
        progress = storage.get_campaign_progress(user["id"])
        next_level = campaign.get_next_level(campaign_level_id)
        result["campaign_result"] = {
            "level_id": campaign_level_id,
            "stars": progress[campaign_level_id]["stars"],
            "earned_stars": stars,
            "best_attempts": progress[campaign_level_id]["best_attempts"],
            "total_stars": campaign.public_catalog(progress)["total_stars"],
            "next_level": campaign.public_level(next_level, progress) if next_level else None,
        }

    persist_authenticated_game(gm)
    result["session_id"] = session_id
    logger.info(f"猜测请求 - 词: '{word}', 相似度: {result.get('similarity', 'N/A')}%, 猜中: {result.get('is_correct', False)}")
    return jsonify(result)


@app.route("/api/give-up", methods=["POST"])
def give_up():
    session_id, gm = get_or_create_session()
    result = gm.give_up()
    persist_authenticated_game(gm)
    result["session_id"] = session_id
    logger.info(f"放弃本轮 - 会话: {session_id}, 答案: 「{result.get('target_word', 'N/A')}」")
    return jsonify(result)


@app.route("/api/status")
def status():
    session_id, gm = get_or_create_session()
    status = gm.get_status()
    status["session_id"] = session_id
    return jsonify(status)


@app.route("/api/reset-game", methods=["POST"])
def reset_game():
    user = get_current_user()
    if user:
        session_id, gm = get_or_create_session()
        if gm.mode == "campaign" and gm.campaign_level_id:
            level = campaign.get_level(gm.campaign_level_id)
            if level:
                gm.start_campaign_level(level["id"], level["target"])
            else:
                gm.reset_full_game()
        else:
            gm.reset_full_game()
        persist_authenticated_game(gm)
        logger.info(f"用户重置游戏: {user['username']}")
        return jsonify({"game_id": session_id, "message": "游戏已重置"})

    session_id = request.args.get("session_id") or request.headers.get("X-Session-ID")
    new_id = str(uuid.uuid4())
    gm = game_manager.GameManager()
    gm.start_new_round()
    sessions[new_id] = gm
    if session_id and session_id in sessions:
        del sessions[session_id]
    logger.info(f"重置游戏: {new_id}, 目标词: 「{gm.target_word}」")
    return jsonify({"game_id": new_id, "message": "游戏已重置"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
