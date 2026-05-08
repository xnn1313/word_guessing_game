import uuid
import logging
import sys
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import game_manager

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
CORS(app)

# 启动时预加载BGE模型，避免首次请求等待过久
import similarity

similarity.get_model()
logger.info("BGE模型已预加载完成")

sessions = {}


def get_or_create_session():
    session_id = request.args.get("session_id") or request.headers.get("X-Session-ID")
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        gm = game_manager.GameManager()
        gm.start_new_round()
        sessions[session_id] = gm
        logger.info(f"创建新会话: {session_id}, 目标词: 「{gm.target_word}」 (活跃会话数: {len(sessions)})")
    return session_id, sessions[session_id]


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/new-game")
def new_game():
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

    result = gm.make_guess(word)
    logger.info(f"猜测请求 - 词: '{word}', 相似度: {result.get('similarity', 'N/A')}%, 猜中: {result.get('is_correct', False)}")
    return jsonify(result)


@app.route("/api/status")
def status():
    session_id, gm = get_or_create_session()
    status = gm.get_status()
    status["session_id"] = session_id
    return jsonify(status)


@app.route("/api/reset-game", methods=["POST"])
def reset_game():
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
