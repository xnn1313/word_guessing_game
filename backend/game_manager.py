import word_bank
import similarity
import config


class GameManager:
    def __init__(self):
        self.target_word = None
        self.target_embedding = None
        self.history = []
        self.correct_words = set()
        self.attempts = 0
        self.game_active = True
        self.mode = "classic"
        self.campaign_level_id = None

    def start_new_round(self):
        exclude = self.correct_words if config.AVOID_REPEAT_TARGET else None
        self.target_word = word_bank.get_random_target(exclude=exclude)
        self.history = []
        self.attempts = 0
        self.game_active = True
        self.mode = "classic"
        self.campaign_level_id = None

    def start_campaign_level(self, level_id, target_word):
        self.target_word = target_word
        self.history = []
        self.attempts = 0
        self.game_active = True
        self.mode = "campaign"
        self.campaign_level_id = level_id

    def make_guess(self, word: str) -> dict:
        if not self.game_active:
            return {"error": "游戏未开始，请先开始新游戏"}

        self.attempts += 1

        in_bank = word_bank.word_in_bank(word)
        sim = similarity.compute_similarity(word, self.target_word)
        is_correct = in_bank and (word == self.target_word)

        self.history.append({"word": word, "similarity": sim})

        extra_msg = ""
        if not in_bank:
            extra_msg = f"（注意：「{word}」不在词库中，不可能是目标词）"

        if is_correct:
            if self.mode == "campaign":
                self.game_active = False
                return {
                    "similarity": sim,
                    "is_correct": True,
                    "attempts": self.attempts,
                    "history": self.history,
                    "correct_count": len(self.correct_words),
                    "target_word": self.target_word,
                    "message": f"🎉 闯关成功！答案是「{self.target_word}」",
                }

            self.correct_words.add(self.target_word)
            if config.AUTO_NEW_ROUND_ON_CORRECT:
                old_target = self.target_word
                self.start_new_round()
                return {
                    "similarity": sim,
                    "is_correct": True,
                    "attempts": 0,
                    "history": [],
                    "correct_count": len(self.correct_words),
                    "target_word": old_target,
                    "message": f"🎉 恭喜你猜中了！目标词是「{old_target}」，已自动切换为新词语",
                }

        msg = extra_msg if extra_msg else "继续加油！"
        return {
            "similarity": sim,
            "is_correct": False,
            "attempts": self.attempts,
            "history": self.history,
            "correct_count": len(self.correct_words),
            "message": msg,
        }

    def give_up(self) -> dict:
        """Reveal the current answer and move to a fresh round."""
        if not self.game_active:
            return {"error": "游戏未开始，请先开始新游戏"}

        old_target = self.target_word
        if self.mode == "campaign":
            level_id = self.campaign_level_id
            self.start_campaign_level(level_id, old_target)
            return {
                "target_word": old_target,
                "attempts": 0,
                "history": [],
                "correct_count": len(self.correct_words),
                "campaign_retry": True,
                "campaign_level_id": level_id,
                "message": f"本关答案是「{old_target}」，已重新开始本关",
            }

        self.start_new_round()
        return {
            "target_word": old_target,
            "attempts": 0,
            "history": [],
            "correct_count": len(self.correct_words),
            "message": f"本轮答案是「{old_target}」，已开始新一轮",
        }

    def reset_full_game(self):
        self.target_word = None
        self.history = []
        self.correct_words = set()
        self.attempts = 0
        self.game_active = True
        self.start_new_round()

    def get_status(self) -> dict:
        return {
            "attempts": self.attempts,
            "history": self.history,
            "correct_count": len(self.correct_words),
            "game_active": self.game_active,
            "mode": self.mode,
            "campaign_level_id": self.campaign_level_id,
        }

    def to_dict(self) -> dict:
        return {
            "target_word": self.target_word,
            "history": self.history,
            "correct_words": sorted(self.correct_words),
            "attempts": self.attempts,
            "game_active": self.game_active,
            "mode": self.mode,
            "campaign_level_id": self.campaign_level_id,
        }

    @classmethod
    def from_dict(cls, state):
        gm = cls()
        if not isinstance(state, dict):
            gm.start_new_round()
            return gm

        valid_words = set(word_bank.load_words())
        target_word = state.get("target_word")
        if target_word not in valid_words:
            gm.start_new_round()
            return gm

        history = []
        for item in state.get("history", []):
            if not isinstance(item, dict) or not isinstance(item.get("word"), str):
                continue
            try:
                similarity_value = float(item.get("similarity", 0))
            except (TypeError, ValueError):
                similarity_value = 0.0
            history.append({"word": item["word"], "similarity": similarity_value})

        gm.target_word = target_word
        gm.history = history
        gm.correct_words = set(state.get("correct_words", [])) & valid_words
        try:
            gm.attempts = max(0, int(state.get("attempts", len(history))))
        except (TypeError, ValueError):
            gm.attempts = len(history)
        gm.game_active = bool(state.get("game_active", True))
        mode = state.get("mode", "classic")
        gm.mode = mode if mode in {"classic", "campaign"} else "classic"
        gm.campaign_level_id = state.get("campaign_level_id") if gm.mode == "campaign" else None
        return gm
