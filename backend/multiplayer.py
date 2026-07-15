import math
import random
import string
import threading
import time

import campaign
import similarity
import storage
import word_bank


ROUND_SECONDS = 90
ROOM_TTL_SECONDS = 2 * 60 * 60
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

rooms = {}
user_rooms = {}
_lock = threading.RLock()


class BattleError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _new_code():
    for _ in range(100):
        code = "".join(random.choices(CODE_ALPHABET, k=6))
        if code not in rooms:
            return code
    raise BattleError("房间码生成失败，请重试", 500)


def _new_player(user):
    return {
        "user_id": user["id"],
        "username": user["username"],
        "joined_at": time.time(),
        "attempts": 0,
        "best_similarity": 0.0,
        "history": [],
        "rematch_ready": False,
    }


def _cleanup_rooms():
    cutoff = time.time() - ROOM_TTL_SECONDS
    expired = [code for code, room in rooms.items() if room["created_at"] < cutoff]
    for code in expired:
        room = rooms.pop(code)
        for user_id in room["players"]:
            if user_rooms.get(user_id) == code:
                del user_rooms[user_id]


def _finish_room(room, winner_id, reason):
    room["state"] = "finished"
    room["winner_id"] = winner_id
    room["finish_reason"] = reason
    room["finished_at"] = time.time()
    for player in room["players"].values():
        player["rematch_ready"] = False


def _select_target(room):
    targets = list(dict.fromkeys(campaign.get_all_targets()))
    if not targets:
        raise BattleError("双人题库为空，暂时无法开始比赛", 500)

    player_ids = list(room["players"])
    last_seen = storage.get_battle_target_last_seen(player_ids)
    candidates = [word for word in targets if word not in last_seen]

    if not candidates:
        oldest_seen_id = min(last_seen[word] for word in targets)
        candidates = [word for word in targets if last_seen[word] == oldest_seen_id]

    target_word = random.choice(candidates)
    storage.record_battle_target(player_ids, target_word)
    return target_word


def _start_round(room):
    room["target_word"] = _select_target(room)
    room["state"] = "playing"
    room["started_at"] = time.time()
    room["ends_at"] = room["started_at"] + ROUND_SECONDS
    room["finished_at"] = None
    room["winner_id"] = None
    room["finish_reason"] = None
    for player in room["players"].values():
        player["attempts"] = 0
        player["best_similarity"] = 0.0
        player["history"] = []
        player["rematch_ready"] = False


def _update_timeout(room):
    if room["state"] != "playing" or time.time() < room["ends_at"]:
        return

    ranked = sorted(
        room["players"].values(),
        key=lambda player: (-player["best_similarity"], player["attempts"], player["joined_at"]),
    )
    winner_id = None
    if ranked:
        if len(ranked) == 1 or (
            ranked[0]["best_similarity"], ranked[0]["attempts"]
        ) != (
            ranked[1]["best_similarity"], ranked[1]["attempts"]
        ):
            winner_id = ranked[0]["user_id"]
    _finish_room(room, winner_id, "timeout")


def _get_room_for_user(user_id, code=None):
    room_code = code or user_rooms.get(user_id)
    room = rooms.get(room_code)
    if not room or user_id not in room["players"]:
        raise BattleError("你当前不在双人房间中", 404)
    _update_timeout(room)
    return room


def _remove_user_from_room(user_id):
    code = user_rooms.get(user_id)
    room = rooms.get(code)
    if not room:
        user_rooms.pop(user_id, None)
        return

    if room["state"] == "playing":
        opponents = [player_id for player_id in room["players"] if player_id != user_id]
        _finish_room(room, opponents[0] if opponents else None, "opponent_left")

    room["players"].pop(user_id, None)
    user_rooms.pop(user_id, None)
    if not room["players"]:
        rooms.pop(code, None)
    elif room["host_id"] == user_id:
        room["host_id"] = next(iter(room["players"]))


def public_state(room, viewer_id):
    _update_timeout(room)
    players = []
    for player in room["players"].values():
        players.append(
            {
                "username": player["username"],
                "is_self": player["user_id"] == viewer_id,
                "is_host": player["user_id"] == room["host_id"],
                "is_winner": player["user_id"] == room["winner_id"],
                "attempts": player["attempts"],
                "best_similarity": player["best_similarity"],
                "rematch_ready": player["rematch_ready"],
            }
        )

    viewer = room["players"].get(viewer_id)
    winner = room["players"].get(room["winner_id"])
    state = {
        "code": room["code"],
        "state": room["state"],
        "is_host": viewer_id == room["host_id"],
        "can_start": room["state"] == "waiting" and viewer_id == room["host_id"] and len(room["players"]) == 2,
        "duration_seconds": ROUND_SECONDS,
        "remaining_seconds": (
            max(0, math.ceil(room["ends_at"] - time.time())) if room["state"] == "playing" else 0
        ),
        "players": players,
        "my_history": list(viewer["history"]) if viewer else [],
        "winner_username": winner["username"] if winner else None,
        "finish_reason": room["finish_reason"],
        "can_rematch": room["state"] == "finished" and len(room["players"]) == 2,
        "rematch_ready": bool(viewer and viewer["rematch_ready"]),
    }
    if room["state"] == "finished":
        state["target_word"] = room["target_word"]
    return state


def create_room(user):
    with _lock:
        _cleanup_rooms()
        existing_code = user_rooms.get(user["id"])
        if existing_code and existing_code in rooms:
            existing = rooms[existing_code]
            _update_timeout(existing)
            if existing["state"] != "finished":
                raise BattleError("你已经在一个双人房间中", 409)
            _remove_user_from_room(user["id"])

        code = _new_code()
        room = {
            "code": code,
            "host_id": user["id"],
            "state": "waiting",
            "target_word": None,
            "players": {user["id"]: _new_player(user)},
            "created_at": time.time(),
            "started_at": None,
            "ends_at": None,
            "finished_at": None,
            "winner_id": None,
            "finish_reason": None,
        }
        rooms[code] = room
        user_rooms[user["id"]] = code
        return public_state(room, user["id"])


def join_room(user, code):
    code = str(code or "").strip().upper()
    with _lock:
        _cleanup_rooms()
        room = rooms.get(code)
        if not room:
            raise BattleError("房间不存在，请检查房间码", 404)
        if user["id"] in room["players"]:
            user_rooms[user["id"]] = code
            return public_state(room, user["id"])
        if room["state"] != "waiting":
            raise BattleError("比赛已经开始，无法加入", 409)
        if len(room["players"]) >= 2:
            raise BattleError("房间人数已满", 409)

        existing_code = user_rooms.get(user["id"])
        if existing_code and existing_code in rooms:
            existing = rooms[existing_code]
            _update_timeout(existing)
            if existing["state"] != "finished":
                raise BattleError("你已经在另一个双人房间中", 409)
            _remove_user_from_room(user["id"])

        room["players"][user["id"]] = _new_player(user)
        user_rooms[user["id"]] = code
        return public_state(room, user["id"])


def start_room(user_id, code=None):
    with _lock:
        room = _get_room_for_user(user_id, code)
        if room["host_id"] != user_id:
            raise BattleError("只有房主可以开始比赛", 403)
        if room["state"] != "waiting":
            raise BattleError("当前房间不能开始比赛", 409)
        if len(room["players"]) != 2:
            raise BattleError("需要两名玩家才能开始", 409)

        _start_round(room)
        return public_state(room, user_id)


def get_current_room(user_id):
    with _lock:
        _cleanup_rooms()
        room = _get_room_for_user(user_id)
        return public_state(room, user_id)


def make_guess(user_id, word):
    word = str(word or "").strip()
    if not word:
        raise BattleError("猜测词不能为空")

    with _lock:
        room = _get_room_for_user(user_id)
        if room["state"] != "playing":
            raise BattleError("比赛尚未开始或已经结束", 409)
        target_word = room["target_word"]
        room_code = room["code"]

    score = similarity.compute_similarity(word, target_word)
    is_correct = word_bank.word_in_bank(word) and word == target_word

    with _lock:
        room = _get_room_for_user(user_id, room_code)
        if room["state"] != "playing" or room["target_word"] != target_word:
            raise BattleError("比赛已经结束", 409)
        player = room["players"][user_id]
        player["attempts"] += 1
        player["best_similarity"] = max(player["best_similarity"], score)
        player["history"].append({"word": word, "similarity": score})
        if is_correct:
            _finish_room(room, user_id, "correct")
        state = public_state(room, user_id)
        state["guess_result"] = {
            "word": word,
            "similarity": score,
            "is_correct": is_correct,
            "in_word_bank": word_bank.word_in_bank(word),
        }
        return state


def leave_room(user_id):
    with _lock:
        room = _get_room_for_user(user_id)
        code = room["code"]
        _remove_user_from_room(user_id)
        return {"message": "已离开房间", "code": code}


def request_rematch(user_id):
    with _lock:
        room = _get_room_for_user(user_id)
        if room["state"] != "finished":
            raise BattleError("当前比赛尚未结束", 409)
        if len(room["players"]) != 2:
            raise BattleError("对手已离开，无法在原房间再来一局", 409)

        room["players"][user_id]["rematch_ready"] = True
        if all(player["rematch_ready"] for player in room["players"].values()):
            _start_round(room)
        return public_state(room, user_id)
