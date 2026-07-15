import json
import random
import os
import config


def load_words():
    path = os.path.join(os.path.dirname(__file__), config.WORD_BANK_FILE)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 闯关词库同时进入相似度校准和经典模式候选池。
    import campaign
    return list(dict.fromkeys(data["words"] + campaign.get_all_targets()))


def get_random_target(exclude=None):
    words = load_words()
    if exclude:
        candidates = [w for w in words if w not in exclude]
        if not candidates:
            candidates = words
    else:
        candidates = words
    return random.choice(candidates)


def word_in_bank(word: str) -> bool:
    words = load_words()
    return word in words
