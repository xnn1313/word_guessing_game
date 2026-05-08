import json
import random
import os
import config


def load_words():
    path = os.path.join(os.path.dirname(__file__), config.WORD_BANK_FILE)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["words"]


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
