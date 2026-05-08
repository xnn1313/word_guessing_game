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

    def start_new_round(self):
        exclude = self.correct_words if config.AVOID_REPEAT_TARGET else None
        self.target_word = word_bank.get_random_target(exclude=exclude)
        self.history = []
        self.attempts = 0
        self.game_active = True

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
        }
