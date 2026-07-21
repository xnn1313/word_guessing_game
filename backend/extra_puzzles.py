"""Poetry quiz, Sokoban and arrow-maze puzzle services.

The three games intentionally reuse the generic ``game_runs`` table so mobile
and web clients get the same authenticated resume semantics as the existing
puzzle collection.  Guest progress remains client-side.
"""

from __future__ import annotations

from collections import deque
from datetime import date as calendar_date
import hashlib
import json
from pathlib import Path
import random
import secrets
from typing import Any, Iterable

import puzzle_games
import storage


DIFFICULTIES = ("easy", "medium", "hard")
MODES = ("daily", "practice")
BOARD_MODES = ("daily", "level", "practice")
EXTRA_LEVEL_COUNT = 20


# Core public-domain works keep the familiar introductory set at the front of
# the catalog.  A frozen chinese-poetry selection is merged below.
CORE_POEMS = [
    ("静夜思", "李白", "唐", ("床前明月光", "疑是地上霜", "举头望明月", "低头思故乡"), 1),
    ("春晓", "孟浩然", "唐", ("春眠不觉晓", "处处闻啼鸟", "夜来风雨声", "花落知多少"), 1),
    ("登鹳雀楼", "王之涣", "唐", ("白日依山尽", "黄河入海流", "欲穷千里目", "更上一层楼"), 1),
    ("悯农", "李绅", "唐", ("锄禾日当午", "汗滴禾下土", "谁知盘中餐", "粒粒皆辛苦"), 1),
    ("咏鹅", "骆宾王", "唐", ("鹅鹅鹅", "曲项向天歌", "白毛浮绿水", "红掌拨清波"), 1),
    ("江雪", "柳宗元", "唐", ("千山鸟飞绝", "万径人踪灭", "孤舟蓑笠翁", "独钓寒江雪"), 1),
    ("相思", "王维", "唐", ("红豆生南国", "春来发几枝", "愿君多采撷", "此物最相思"), 1),
    ("寻隐者不遇", "贾岛", "唐", ("松下问童子", "言师采药去", "只在此山中", "云深不知处"), 1),
    ("早发白帝城", "李白", "唐", ("朝辞白帝彩云间", "千里江陵一日还", "两岸猿声啼不住", "轻舟已过万重山"), 1),
    ("望庐山瀑布", "李白", "唐", ("日照香炉生紫烟", "遥看瀑布挂前川", "飞流直下三千尺", "疑是银河落九天"), 1),
    ("绝句", "杜甫", "唐", ("两个黄鹂鸣翠柳", "一行白鹭上青天", "窗含西岭千秋雪", "门泊东吴万里船"), 1),
    ("小池", "杨万里", "宋", ("泉眼无声惜细流", "树阴照水爱晴柔", "小荷才露尖尖角", "早有蜻蜓立上头"), 1),
    ("枫桥夜泊", "张继", "唐", ("月落乌啼霜满天", "江枫渔火对愁眠", "姑苏城外寒山寺", "夜半钟声到客船"), 2),
    ("山行", "杜牧", "唐", ("远上寒山石径斜", "白云生处有人家", "停车坐爱枫林晚", "霜叶红于二月花"), 2),
    ("游子吟", "孟郊", "唐", ("慈母手中线", "游子身上衣", "临行密密缝", "意恐迟迟归", "谁言寸草心", "报得三春晖"), 2),
    ("题西林壁", "苏轼", "宋", ("横看成岭侧成峰", "远近高低各不同", "不识庐山真面目", "只缘身在此山中"), 2),
    ("泊船瓜洲", "王安石", "宋", ("京口瓜洲一水间", "钟山只隔数重山", "春风又绿江南岸", "明月何时照我还"), 2),
    ("竹石", "郑燮", "清", ("咬定青山不放松", "立根原在破岩中", "千磨万击还坚劲", "任尔东西南北风"), 2),
    ("石灰吟", "于谦", "明", ("千锤万凿出深山", "烈火焚烧若等闲", "粉骨碎身浑不怕", "要留清白在人间"), 2),
    ("饮湖上初晴后雨", "苏轼", "宋", ("水光潋滟晴方好", "山色空蒙雨亦奇", "欲把西湖比西子", "淡妆浓抹总相宜"), 2),
    ("清明", "杜牧", "唐", ("清明时节雨纷纷", "路上行人欲断魂", "借问酒家何处有", "牧童遥指杏花村"), 2),
    ("送元二使安西", "王维", "唐", ("渭城朝雨浥轻尘", "客舍青青柳色新", "劝君更尽一杯酒", "西出阳关无故人"), 2),
    ("黄鹤楼送孟浩然之广陵", "李白", "唐", ("故人西辞黄鹤楼", "烟花三月下扬州", "孤帆远影碧空尽", "唯见长江天际流"), 2),
    ("赠汪伦", "李白", "唐", ("李白乘舟将欲行", "忽闻岸上踏歌声", "桃花潭水深千尺", "不及汪伦送我情"), 2),
    ("江南春", "杜牧", "唐", ("千里莺啼绿映红", "水村山郭酒旗风", "南朝四百八十寺", "多少楼台烟雨中"), 2),
    ("村居", "高鼎", "清", ("草长莺飞二月天", "拂堤杨柳醉春烟", "儿童散学归来早", "忙趁东风放纸鸢"), 2),
    ("乌衣巷", "刘禹锡", "唐", ("朱雀桥边野草花", "乌衣巷口夕阳斜", "旧时王谢堂前燕", "飞入寻常百姓家"), 3),
    ("赤壁", "杜牧", "唐", ("折戟沉沙铁未销", "自将磨洗认前朝", "东风不与周郎便", "铜雀春深锁二乔"), 3),
    ("泊秦淮", "杜牧", "唐", ("烟笼寒水月笼沙", "夜泊秦淮近酒家", "商女不知亡国恨", "隔江犹唱后庭花"), 3),
    ("夜雨寄北", "李商隐", "唐", ("君问归期未有期", "巴山夜雨涨秋池", "何当共剪西窗烛", "却话巴山夜雨时"), 3),
    ("滁州西涧", "韦应物", "唐", ("独怜幽草涧边生", "上有黄鹂深树鸣", "春潮带雨晚来急", "野渡无人舟自横"), 3),
    ("凉州词", "王翰", "唐", ("葡萄美酒夜光杯", "欲饮琵琶马上催", "醉卧沙场君莫笑", "古来征战几人回"), 3),
    ("从军行", "王昌龄", "唐", ("青海长云暗雪山", "孤城遥望玉门关", "黄沙百战穿金甲", "不破楼兰终不还"), 3),
    ("出塞", "王昌龄", "唐", ("秦时明月汉时关", "万里长征人未还", "但使龙城飞将在", "不教胡马度阴山"), 3),
    ("己亥杂诗", "龚自珍", "清", ("九州生气恃风雷", "万马齐喑究可哀", "我劝天公重抖擞", "不拘一格降人才"), 3),
    ("论诗", "赵翼", "清", ("李杜诗篇万口传", "至今已觉不新鲜", "江山代有才人出", "各领风骚数百年"), 3),
    ("秋夕", "杜牧", "唐", ("银烛秋光冷画屏", "轻罗小扇扑流萤", "天阶夜色凉如水", "卧看牵牛织女星"), 3),
    ("嫦娥", "李商隐", "唐", ("云母屏风烛影深", "长河渐落晓星沉", "嫦娥应悔偷灵药", "碧海青天夜夜心"), 3),
]

POETRY_BANK_PATH = Path(__file__).resolve().parent / "data" / "poetry_bank.json"
POETRY_QUESTION_COUNTS = {"easy": 12, "medium": 20, "hard": 30}
POETRY_CATALOG_VERSION = "2026.07-xl"
POETRY_DYNASTIES = ("先秦", "汉", "魏晋", "唐", "宋", "元", "明", "清")
POETRY_THEME_RULES = (
    (("故乡", "乡", "归", "客", "独", "明月"), "借异乡见闻、归意或月色寄托思念与羁旅感受"),
    (("送", "别", "故人", "孤帆", "长亭", "阳关"), "从送别场景落笔，写人与人之间的不舍和牵挂"),
    (("关", "塞", "征", "沙场", "胡马", "玉门", "金甲"), "描写边塞与征战，表现守卫、思归或战争带来的复杂情感"),
    (("春", "花", "柳", "莺", "燕", "东风"), "捕捉春日草木与风物的变化，写出生命萌发和时光流转"),
    (("秋", "霜", "落叶", "雁", "寒", "暮"), "借秋景与寒意营造氛围，寄托感时、怀人或身世之思"),
    (("山", "水", "江", "湖", "云", "雨", "雪"), "铺展山水气象，把眼前景色与内心感受交织在一起"),
    (("田", "农", "禾", "耕", "桑", "锄"), "关注田园与劳作，在日常生活中体会劳动、节令和民生"),
    (("坚", "志", "不怕", "清白", "千磨", "凌云"), "借物或叙事表达志向，突出坚定、不屈和自我期许"),
)


def _load_external_poems() -> list[tuple[str, str, str, tuple[str, ...], int]]:
    try:
        with POETRY_BANK_PATH.open(encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot load poetry bank: {POETRY_BANK_PATH}") from error
    if payload.get("metadata", {}).get("schema_version") != 1 or not isinstance(payload.get("poems"), list):
        raise RuntimeError("poetry bank schema is invalid")

    poems = []
    for raw in payload["poems"]:
        try:
            title = str(raw["title"]).strip()
            author = str(raw["author"]).strip()
            dynasty = str(raw["dynasty"]).strip()
            lines = tuple(str(line).strip() for line in raw["lines"] if str(line).strip())
            level = int(raw["level"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("poetry bank contains an invalid record") from error
        if not title or not author or dynasty not in POETRY_DYNASTIES or len(lines) < 2 or level not in {1, 2, 3}:
            raise RuntimeError("poetry bank contains an invalid record")
        poems.append((title, author, dynasty, lines, level))
    return poems


def _merge_poems():
    merged = []
    seen = set()
    for poem in [*CORE_POEMS, *_load_external_poems()]:
        identity = poem[:4]
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(poem)
    return merged


POEMS = _merge_poems()
POETRY_POOL_SIZES = {
    difficulty: sum(1 for poem in POEMS if poem[4] <= index + 1)
    for index, difficulty in enumerate(DIFFICULTIES)
}


ARROWS = (
    (-1, 0, "↑"),
    (-1, 1, "↗"),
    (0, 1, "→"),
    (1, 1, "↘"),
    (1, 0, "↓"),
    (1, -1, "↙"),
    (0, -1, "←"),
    (-1, -1, "↖"),
)
MOVE_DELTAS = {"U": (-1, 0), "R": (0, 1), "D": (1, 0), "L": (0, -1)}
SOKOBAN_SETTINGS = {
    "easy": {"size": 6, "boxes": 1, "pulls": 4, "walls": 0},
    "medium": {"size": 7, "boxes": 2, "pulls": 8, "walls": 2},
    "hard": {"size": 8, "boxes": 3, "pulls": 13, "walls": 4},
}
ARROW_SETTINGS = {
    "easy": {"size": 5, "minimum": 3, "maximum": 5, "diagonal": False},
    "medium": {"size": 6, "minimum": 5, "maximum": 8, "diagonal": True},
    "hard": {"size": 7, "minimum": 7, "maximum": 12, "diagonal": True},
}


def _choice(value: Any, values: Iterable[str], field: str) -> str:
    return puzzle_games._choice(value, set(values), field)


def _integer(data: dict[str, Any], field: str, minimum=0, maximum=None, default=None) -> int:
    return puzzle_games._integer(data, field, minimum, maximum, default)


def _rng(seed: str) -> random.Random:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def _daily_id(game_key: str, difficulty: str) -> tuple[str, str]:
    date = puzzle_games.server_date()
    current = storage.get_daily_puzzle_id(game_key, date, difficulty)
    if current:
        return current, date
    puzzle_id = f"{game_key}-{date}-{difficulty}"
    return storage.set_daily_puzzle_id(game_key, date, difficulty, puzzle_id), date


def _select_puzzle_id(
    user: dict[str, Any] | None,
    game_key: str,
    mode: str,
    difficulty: str,
    fresh: bool,
) -> tuple[str, str | None]:
    if mode == "daily":
        return _daily_id(game_key, difficulty)
    if user and not fresh:
        resumed = storage.get_latest_playing_run(user["id"], game_key, mode, difficulty)
        if resumed and (
            game_key != "poetry" or f"poetry-practice-{POETRY_CATALOG_VERSION}-" in resumed["puzzle_id"]
        ):
            return resumed["puzzle_id"], None
    version = f"-{POETRY_CATALOG_VERSION}" if game_key == "poetry" else ""
    return f"{game_key}-practice{version}-{difficulty}-{secrets.token_hex(5)}", None


def _level_puzzle_id(game_key: str, difficulty: str, level_order: int) -> str:
    return f"{game_key}-level-{difficulty}-{level_order:02d}"


def _level_order_from_puzzle_id(puzzle_id: str, game_key: str, difficulty: str) -> int | None:
    prefix = f"{game_key}-level-{difficulty}-"
    if not puzzle_id.startswith(prefix):
        return None
    try:
        level_order = int(puzzle_id[len(prefix) :])
    except ValueError:
        return None
    return level_order if 1 <= level_order <= EXTRA_LEVEL_COUNT else None


def get_level_catalog(user, game_key: str) -> dict[str, Any]:
    if game_key not in {"sokoban", "arrow_maze"}:
        raise puzzle_games.PuzzleError("不支持的闯关游戏", "INVALID_GAME")
    progress = storage.get_level_progress(user["id"], game_key) if user else {}
    difficulties = []
    total_stars = 0
    for difficulty in DIFFICULTIES:
        levels = []
        previous_completed = True
        completed_levels = 0
        for level_order in range(1, EXTRA_LEVEL_COUNT + 1):
            puzzle_id = _level_puzzle_id(game_key, difficulty, level_order)
            result = progress.get(puzzle_id, {})
            stars = int(result.get("stars") or 0)
            unlocked = level_order == 1 or previous_completed
            levels.append(
                {
                    "order": level_order,
                    "puzzle_id": puzzle_id,
                    "unlocked": unlocked,
                    "stars": stars,
                    "best_score": result.get("best_score"),
                }
            )
            if stars > 0:
                completed_levels += 1
                total_stars += stars
            previous_completed = stars > 0
        difficulties.append(
            {
                "key": difficulty,
                "completed_levels": completed_levels,
                "total_levels": EXTRA_LEVEL_COUNT,
                "levels": levels,
            }
        )
    return {
        "game_key": game_key,
        "total_stars": total_stars,
        "max_stars": EXTRA_LEVEL_COUNT * len(DIFFICULTIES) * 3,
        "difficulties": difficulties,
    }


def _select_board_puzzle_id(user, game_key: str, mode: str, difficulty: str, fresh: bool, level_order):
    if mode != "level":
        puzzle_id, date = _select_puzzle_id(user, game_key, mode, difficulty, fresh)
        return puzzle_id, date, None
    order = _integer({"level_order": level_order}, "level_order", 1, EXTRA_LEVEL_COUNT, 1)
    if user:
        catalog = get_level_catalog(user, game_key)
        difficulty_catalog = next(item for item in catalog["difficulties"] if item["key"] == difficulty)
        if not difficulty_catalog["levels"][order - 1]["unlocked"]:
            raise puzzle_games.PuzzleError("请先完成上一关", "LEVEL_LOCKED", 403)
    return _level_puzzle_id(game_key, difficulty, order), None, order


def ensure_daily_puzzles() -> None:
    for game_key in ("poetry", "sokoban", "arrow_maze"):
        _daily_id(game_key, "medium")


def _public_run_state(run: dict[str, Any] | None, fields: Iterable[str]) -> dict[str, Any] | None:
    if not run:
        return None
    state = {field: run["state"].get(field) for field in fields}
    state.update(
        {
            "elapsed_seconds": run["elapsed_seconds"],
            "hints_used": run["hints_used"],
            "mistakes": run["mistakes"],
        }
    )
    return state


# ---------------------------------------------------------------------------
# Poetry quiz


def _poetry_pool(difficulty: str):
    level = DIFFICULTIES.index(difficulty) + 1
    return [poem for poem in POEMS if poem[4] <= level]


def _poetry_daily_date(puzzle_id: str) -> calendar_date | None:
    prefix = "poetry-"
    if not puzzle_id.startswith(prefix):
        return None
    # Daily IDs are poetry-YYYY-MM-DD-difficulty.  Practice IDs deliberately
    # miss this parse and use independent random sampling.
    try:
        return calendar_date.fromisoformat(puzzle_id[len(prefix) : len(prefix) + 10])
    except ValueError:
        return None


def _select_poetry_group(puzzle_id: str, difficulty: str, eligible, total: int, rng):
    daily_date = _poetry_daily_date(puzzle_id)
    if not daily_date:
        return rng.sample(eligible, total)

    # One stable shuffle plus a daily stride gives disjoint adjacent groups.
    # Every work is used, including the final partial block, and a work cannot
    # reappear for at least floor(catalog_size / question_count) days.
    rotation = list(eligible)
    _rng(f"poetry:{POETRY_CATALOG_VERSION}:{difficulty}:rotation").shuffle(rotation)
    start = (daily_date.toordinal() * total) % len(rotation)
    return [rotation[(start + offset) % len(rotation)] for offset in range(total)]


def _poetry_questions(puzzle_id: str, difficulty: str) -> list[dict[str, Any]]:
    rng = _rng(puzzle_id)
    eligible = _poetry_pool(difficulty)
    total = POETRY_QUESTION_COUNTS[difficulty]
    selected = _select_poetry_group(puzzle_id, difficulty, eligible, total, rng)
    questions = []
    allowed_types = {
        "easy": ("next", "previous"),
        "medium": ("next", "previous", "author", "title"),
        "hard": ("next", "previous", "author", "title", "dynasty"),
    }[difficulty]
    for index, poem in enumerate(selected):
        title, author, dynasty, lines, _ = poem
        question_type = allowed_types[index % len(allowed_types)]
        if question_type in {"next", "previous"}:
            pair_index = rng.randrange(len(lines) - 1)
            if question_type == "next":
                prompt = "接出下一句"
                context = lines[pair_index]
                answer = lines[pair_index + 1]
                pool = [other[3][min(pair_index + 1, len(other[3]) - 1)] for other in eligible]
            else:
                prompt = "找出上一句"
                context = lines[pair_index + 1]
                answer = lines[pair_index]
                pool = [other[3][min(pair_index, len(other[3]) - 1)] for other in eligible]
        elif question_type == "author":
            prompt = "这首诗出自谁"
            context = f"《{title}》\n{lines[0]}"
            answer = author
            pool = [other[1] for other in eligible]
        elif question_type == "title":
            prompt = "根据诗句选诗名"
            context = f"{lines[0]}，{lines[1]}"
            answer = title
            pool = [other[0] for other in eligible]
        else:
            prompt = "判断作品朝代"
            context = f"《{title}》· {author}"
            answer = dynasty
            pool = list(POETRY_DYNASTIES)
        distractors = []
        for candidate in pool:
            if candidate != answer and candidate not in distractors:
                distractors.append(candidate)
        rng.shuffle(distractors)
        options = [answer, *distractors[:3]]
        rng.shuffle(options)
        poem_text = "".join(lines)
        matched_terms = []
        theme_notes = []
        for keywords, note in POETRY_THEME_RULES:
            hits = [keyword for keyword in keywords if keyword in poem_text]
            if hits:
                matched_terms.extend(hit for hit in hits if hit not in matched_terms)
                if note not in theme_notes:
                    theme_notes.append(note)
            if len(theme_notes) >= 2:
                break
        meaning = "；也".join(theme_notes) if theme_notes else "从具体的人、事、景落笔，把画面、动作和情感凝练在诗句中"
        excerpt_lines = list(lines[:6])
        questions.append(
            {
                "id": f"{puzzle_id}:{index}",
                "type": question_type,
                "prompt": prompt,
                "context": context,
                "options": options,
                "answer": answer,
                "explanation": f"{dynasty} · {author}《{title}》",
                "study": {
                    "source": f"{dynasty} · {author}《{title}》",
                    "excerpt": "\n".join(excerpt_lines),
                    "meaning": f"这首作品{meaning}。把本题句子放回完整语境中读，更容易理解句序和作者要表达的情绪。",
                    "key_terms": "、".join(matched_terms[:5]) if matched_terms else "画面、动作、语气、情感",
                },
            }
        )
    return questions


def _poetry_question_public(question: dict[str, Any], index: int, total: int) -> dict[str, Any]:
    return {
        key: question[key]
        for key in ("id", "type", "prompt", "context", "options")
    } | {"index": index, "total": total}


def get_poetry(user, mode, difficulty, fresh=False):
    mode = _choice(mode, MODES, "mode")
    difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
    puzzle_id, date = _select_puzzle_id(user, "poetry", mode, difficulty, fresh)
    questions = _poetry_questions(puzzle_id, difficulty)
    run = puzzle_games._run_for_puzzle(
        user,
        "poetry",
        puzzle_id,
        mode,
        difficulty,
        {"question_index": 0, "correct_count": 0},
    )
    index = min(int(run["state"].get("question_index", 0)) if run else 0, len(questions) - 1)
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "question_count": len(questions),
        "catalog_size": len(_poetry_pool(difficulty)),
        "rotation_days": len(_poetry_pool(difficulty)) // len(questions),
        "question": _poetry_question_public(questions[index], index, len(questions)),
        "run_id": run["id"] if run else None,
        "saved_state": _public_run_state(run, ("question_index", "correct_count")),
    }


def save_poetry(user, data):
    if not user:
        raise puzzle_games.PuzzleError("登录后才能使用云存档", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id") or "")
    run = puzzle_games._owned_run(user, data.get("run_id"), "poetry", puzzle_id)
    if not run:
        raise puzzle_games.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    questions = _poetry_questions(puzzle_id, run["difficulty"])
    index = _integer(data, "question_index", 0, len(questions), 0)
    correct = _integer(data, "correct_count", 0, len(questions), 0)
    mistakes = _integer(data, "mistakes", 0, len(questions), 0)
    if index < int(run["state"].get("question_index", 0)) or correct < int(run["state"].get("correct_count", 0)):
        raise puzzle_games.PuzzleError("答题进度不能回退", "PROGRESS_REGRESSION")
    timestamp = puzzle_games._save_state(
        run,
        user,
        {"question_index": index, "correct_count": correct},
        puzzle_games._elapsed(data),
        0,
        mistakes,
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def submit_poetry(user, data):
    puzzle_id = str(data.get("puzzle_id") or "")
    difficulty = _choice(data.get("difficulty"), DIFFICULTIES, "difficulty")
    questions = _poetry_questions(puzzle_id, difficulty)
    index = _integer(data, "question_index", 0, len(questions) - 1, 0)
    question = questions[index]
    if str(data.get("question_id") or "") != question["id"]:
        raise puzzle_games.PuzzleError("题目位置已经变化，请刷新后重试", "QUESTION_CONFLICT", 409)
    answer = str(data.get("answer") or "").strip()
    if answer not in question["options"]:
        raise puzzle_games.PuzzleError("请选择一个有效答案", "INVALID_ANSWER")
    run = puzzle_games._owned_run(user, data.get("run_id"), "poetry", puzzle_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "poetry", puzzle_id)
    if run:
        original = puzzle_games._idempotent_result(run)
        if original:
            return original
        saved_index = int(run["state"].get("question_index", 0))
        if index != saved_index:
            raise puzzle_games.PuzzleError("该题已经作答，请继续下一题", "QUESTION_CONFLICT", 409)
    correct = answer == question["answer"]
    previous_correct = int(run["state"].get("correct_count", 0)) if run else _integer(
        data, "correct_count", 0, len(questions), 0
    )
    correct_count = previous_correct + (1 if correct else 0)
    mistakes = (run["mistakes"] if run else _integer(data, "mistakes", 0, len(questions), 0)) + (0 if correct else 1)
    next_index = index + 1
    elapsed = max(run["elapsed_seconds"] if run else 0, puzzle_games._elapsed(data))
    response = {
        "correct": correct,
        "correct_answer": question["answer"],
        "explanation": question["explanation"],
        "study": question["study"],
        "correct_count": correct_count,
        "mistakes": mistakes,
    }
    if next_index < len(questions):
        state = {"question_index": next_index, "correct_count": correct_count}
        if run:
            puzzle_games._save_state(run, user, state, elapsed, 0, mistakes)
        return response | {
            "status": "playing",
            "next_question": _poetry_question_public(questions[next_index], next_index, len(questions)),
        }
    score = max(100, correct_count * 220 - elapsed - mistakes * 35)
    accuracy = correct_count / len(questions)
    stars = 3 if accuracy == 1 else 2 if accuracy >= 0.8 else 1
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "mistakes": mistakes,
        "correct_count": correct_count,
        "total_questions": len(questions),
        "is_new_best": bool(user and puzzle_games._is_new_best(user["id"], "poetry", score)),
    }
    if run:
        state = {"question_index": len(questions), "correct_count": correct_count, "result": result}
        completed, saved_run = storage.complete_game_run(
            run["id"], user["id"], state, elapsed, 0, mistakes, score, stars
        )
        if not completed:
            return puzzle_games._idempotent_result(saved_run) or response | {"status": "completed", "result": result}
    return response | {"status": "completed", "result": result}


# ---------------------------------------------------------------------------
# Sokoban


def _neighbors(position: tuple[int, int]):
    row, column = position
    for code, (dr, dc) in MOVE_DELTAS.items():
        yield code, (row + dr, column + dc)


def _reachable(start, walls, boxes, size):
    queue = deque([start])
    seen = {start}
    while queue:
        current = queue.popleft()
        for _, target in _neighbors(current):
            if target in seen or target in walls or target in boxes:
                continue
            if not (0 <= target[0] < size and 0 <= target[1] < size):
                continue
            seen.add(target)
            queue.append(target)
    return seen


def _connected_floor(size, walls):
    floors = {(row, column) for row in range(1, size - 1) for column in range(1, size - 1)} - walls
    if not floors:
        return False
    return _reachable(next(iter(floors)), walls, set(), size) == floors


def _generate_sokoban(puzzle_id: str, difficulty: str) -> dict[str, Any]:
    settings = SOKOBAN_SETTINGS[difficulty]
    size = settings["size"]
    rng = _rng(puzzle_id)
    outer_walls = {
        (row, column)
        for row in range(size)
        for column in range(size)
        if row in {0, size - 1} or column in {0, size - 1}
    }
    interiors = [(row, column) for row in range(1, size - 1) for column in range(1, size - 1)]
    for _ in range(160):
        internal = set(rng.sample(interiors, settings["walls"])) if settings["walls"] else set()
        walls = outer_walls | internal
        if not _connected_floor(size, walls):
            continue
        available = [cell for cell in interiors if cell not in walls]
        targets = set(rng.sample(available, settings["boxes"]))
        boxes = set(targets)
        player = rng.choice([cell for cell in available if cell not in boxes])
        successful = 0
        last_move = None
        for _step in range(settings["pulls"] * 5):
            reachable = _reachable(player, walls, boxes, size)
            candidates = []
            for box in boxes:
                for code, (dr, dc) in MOVE_DELTAS.items():
                    near = (box[0] - dr, box[1] - dc)
                    behind = (box[0] - 2 * dr, box[1] - 2 * dc)
                    if near not in reachable or behind in walls or behind in boxes:
                        continue
                    if not (0 <= behind[0] < size and 0 <= behind[1] < size):
                        continue
                    if last_move and last_move == (box, {"U": "D", "D": "U", "L": "R", "R": "L"}[code]):
                        continue
                    candidates.append((box, code, near, behind))
            if not candidates:
                break
            box, code, near, behind = rng.choice(candidates)
            boxes.remove(box)
            boxes.add(near)
            player = behind
            successful += 1
            last_move = (near, code)
            if successful >= settings["pulls"]:
                break
        if successful >= settings["pulls"] and boxes != targets:
            return {
                "size": size,
                "walls": walls,
                "targets": targets,
                "boxes": boxes,
                "player": player,
                "par_pushes": successful,
            }
    raise puzzle_games.PuzzleError("推箱子关卡生成失败，请换一关", "PUZZLE_GENERATION_FAILED", 500)


def _sokoban_rows(level):
    rows = []
    for row in range(level["size"]):
        values = []
        for column in range(level["size"]):
            cell = (row, column)
            if cell in level["walls"]:
                value = "#"
            elif cell == level["player"] and cell in level["targets"]:
                value = "+"
            elif cell == level["player"]:
                value = "@"
            elif cell in level["boxes"] and cell in level["targets"]:
                value = "*"
            elif cell in level["boxes"]:
                value = "$"
            elif cell in level["targets"]:
                value = "."
            else:
                value = " "
            values.append(value)
        rows.append("".join(values))
    return rows


def _sokoban_replay(level, history: str):
    if not isinstance(history, str) or len(history) > 5000 or any(code not in MOVE_DELTAS for code in history):
        raise puzzle_games.PuzzleError("移动记录格式无效", "INVALID_MOVE_HISTORY")
    player = level["player"]
    boxes = set(level["boxes"])
    moves = pushes = 0
    for code in history:
        dr, dc = MOVE_DELTAS[code]
        target = (player[0] + dr, player[1] + dc)
        if target in level["walls"]:
            raise puzzle_games.PuzzleError("移动记录包含穿墙操作", "INVALID_MOVE_HISTORY")
        if target in boxes:
            beyond = (target[0] + dr, target[1] + dc)
            if beyond in level["walls"] or beyond in boxes:
                raise puzzle_games.PuzzleError("移动记录包含无效推箱操作", "INVALID_MOVE_HISTORY")
            boxes.remove(target)
            boxes.add(beyond)
            pushes += 1
        player = target
        moves += 1
    return {"player": player, "boxes": boxes, "moves": moves, "pushes": pushes}


def get_sokoban(user, mode, difficulty, fresh=False, level_order=None):
    mode = _choice(mode, BOARD_MODES, "mode")
    difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
    puzzle_id, date, selected_level = _select_board_puzzle_id(
        user, "sokoban", mode, difficulty, fresh, level_order
    )
    level = _generate_sokoban(puzzle_id, difficulty)
    run = puzzle_games._run_for_puzzle(user, "sokoban", puzzle_id, mode, difficulty, {"history": ""})
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "level_order": selected_level,
        "level_count": EXTRA_LEVEL_COUNT if mode == "level" else None,
        "rows": level["size"],
        "columns": level["size"],
        "board": _sokoban_rows(level),
        "box_count": len(level["boxes"]),
        "par_pushes": level["par_pushes"],
        "run_id": run["id"] if run else None,
        "saved_state": _public_run_state(run, ("history",)),
    }


def save_sokoban(user, data):
    if not user:
        raise puzzle_games.PuzzleError("登录后才能使用云存档", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id") or "")
    run = puzzle_games._owned_run(user, data.get("run_id"), "sokoban", puzzle_id)
    if not run:
        raise puzzle_games.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    level = _generate_sokoban(puzzle_id, run["difficulty"])
    history = str(data.get("history") or "")
    _sokoban_replay(level, history)
    timestamp = puzzle_games._save_state(
        run,
        user,
        {"history": history},
        puzzle_games._elapsed(data),
        0,
        _integer(data, "mistakes", 0, 100000, 0),
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def submit_sokoban(user, data):
    puzzle_id = str(data.get("puzzle_id") or "")
    difficulty = _choice(data.get("difficulty"), DIFFICULTIES, "difficulty")
    level = _generate_sokoban(puzzle_id, difficulty)
    history = str(data.get("history") or "")
    state = _sokoban_replay(level, history)
    run = puzzle_games._owned_run(user, data.get("run_id"), "sokoban", puzzle_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "sokoban", puzzle_id)
    if run:
        original = puzzle_games._idempotent_result(run)
        if original:
            return original
    if state["boxes"] != level["targets"]:
        return {"correct": False, "status": "playing", "remaining_boxes": len(state["boxes"] - level["targets"])}
    elapsed = max(run["elapsed_seconds"] if run else 0, puzzle_games._elapsed(data))
    mistakes = max(run["mistakes"] if run else 0, _integer(data, "mistakes", 0, 100000, 0))
    score = max(100, 2600 - state["moves"] * 5 - state["pushes"] * 15 - elapsed - mistakes * 30)
    stars = 3 if state["pushes"] <= level["par_pushes"] else 2 if state["pushes"] <= level["par_pushes"] * 1.5 else 1
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "moves": state["moves"],
        "pushes": state["pushes"],
        "mistakes": mistakes,
        "is_new_best": bool(user and puzzle_games._is_new_best(user["id"], "sokoban", score)),
    }
    level_order = _level_order_from_puzzle_id(puzzle_id, "sokoban", difficulty)
    if level_order:
        result["level_order"] = level_order
        result["next_level_order"] = level_order + 1 if level_order < EXTRA_LEVEL_COUNT else None
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"], user["id"], {"history": history, "result": result}, elapsed, 0, mistakes, score, stars
        )
        if not completed:
            return puzzle_games._idempotent_result(saved_run) or {"correct": True, "status": "completed", "result": result}
    return {"correct": True, "status": "completed", "result": result}


# ---------------------------------------------------------------------------
# Arrow maze: move to any cell along the direction shown in the current cell.


def _arrow_moves(index: int, grid: list[int], size: int):
    if index == size * size - 1:
        return []
    direction = grid[index]
    dr, dc, _ = ARROWS[direction]
    row, column = divmod(index, size)
    moves = []
    row += dr
    column += dc
    while 0 <= row < size and 0 <= column < size:
        moves.append(row * size + column)
        row += dr
        column += dc
    return moves


def _arrow_solution(grid: list[int], size: int, start=0):
    target = size * size - 1
    queue = deque([start])
    parents = {start: None}
    while queue:
        current = queue.popleft()
        if current == target:
            path = []
            while current is not None:
                path.append(current)
                current = parents[current]
            return list(reversed(path))
        for next_index in _arrow_moves(current, grid, size):
            if next_index not in parents:
                parents[next_index] = current
                queue.append(next_index)
    return None


def _generate_arrow_maze(puzzle_id: str, difficulty: str):
    settings = ARROW_SETTINGS[difficulty]
    size = settings["size"]
    rng = _rng(puzzle_id)
    direction_pool = list(range(8)) if settings["diagonal"] else [0, 2, 4, 6]
    fallback = None
    for _ in range(6000):
        grid = [rng.choice(direction_pool) for _ in range(size * size)]
        solution = _arrow_solution(grid, size)
        if solution:
            fallback = (grid, solution)
            steps = len(solution) - 1
            if settings["minimum"] <= steps <= settings["maximum"]:
                return grid, solution
    if fallback:
        return fallback
    raise puzzle_games.PuzzleError("箭头迷宫生成失败，请换一盘", "PUZZLE_GENERATION_FAILED", 500)


def _arrow_public_grid(grid, size):
    target = size * size - 1
    return ["◎" if index == target else ARROWS[value][2] for index, value in enumerate(grid)]


def _validate_arrow_path(path, grid, size):
    if not isinstance(path, list) or not path or len(path) > size * size * 4:
        raise puzzle_games.PuzzleError("路径格式无效", "INVALID_PATH")
    normalized = []
    for value in path:
        if isinstance(value, bool):
            raise puzzle_games.PuzzleError("路径格式无效", "INVALID_PATH")
        try:
            index = int(value)
        except (TypeError, ValueError):
            raise puzzle_games.PuzzleError("路径格式无效", "INVALID_PATH") from None
        if not 0 <= index < size * size:
            raise puzzle_games.PuzzleError("路径越出棋盘", "INVALID_PATH")
        normalized.append(index)
    if normalized[0] != 0:
        raise puzzle_games.PuzzleError("路径必须从起点开始", "INVALID_PATH")
    for current, target in zip(normalized, normalized[1:]):
        if target not in _arrow_moves(current, grid, size):
            raise puzzle_games.PuzzleError("路径没有沿箭头方向移动", "INVALID_PATH")
    return normalized


def get_arrow_maze(user, mode, difficulty, fresh=False, level_order=None):
    mode = _choice(mode, BOARD_MODES, "mode")
    difficulty = _choice(difficulty, DIFFICULTIES, "difficulty")
    puzzle_id, date, selected_level = _select_board_puzzle_id(
        user, "arrow_maze", mode, difficulty, fresh, level_order
    )
    grid, solution = _generate_arrow_maze(puzzle_id, difficulty)
    size = ARROW_SETTINGS[difficulty]["size"]
    run = puzzle_games._run_for_puzzle(user, "arrow_maze", puzzle_id, mode, difficulty, {"path": [0]})
    return {
        "puzzle_id": puzzle_id,
        "mode": mode,
        "puzzle_date": date,
        "difficulty": difficulty,
        "level_order": selected_level,
        "level_count": EXTRA_LEVEL_COUNT if mode == "level" else None,
        "rows": size,
        "columns": size,
        "grid": _arrow_public_grid(grid, size),
        "start_index": 0,
        "target_index": size * size - 1,
        "optimal_steps": len(solution) - 1,
        "run_id": run["id"] if run else None,
        "saved_state": _public_run_state(run, ("path",)),
    }


def save_arrow_maze(user, data):
    if not user:
        raise puzzle_games.PuzzleError("登录后才能使用云存档", "AUTH_REQUIRED", 401)
    puzzle_id = str(data.get("puzzle_id") or "")
    run = puzzle_games._owned_run(user, data.get("run_id"), "arrow_maze", puzzle_id)
    if not run:
        raise puzzle_games.PuzzleError("run_id 不能为空", "RUN_ID_REQUIRED")
    grid, _ = _generate_arrow_maze(puzzle_id, run["difficulty"])
    size = ARROW_SETTINGS[run["difficulty"]]["size"]
    path = _validate_arrow_path(data.get("path"), grid, size)
    timestamp = puzzle_games._save_state(
        run,
        user,
        {"path": path},
        puzzle_games._elapsed(data),
        _integer(data, "hints_used", 0, 1000, 0),
        _integer(data, "mistakes", 0, 100000, 0),
    )
    return {"saved": True, "run_id": run["id"], "updated_at": timestamp}


def hint_arrow_maze(user, data):
    puzzle_id = str(data.get("puzzle_id") or "")
    difficulty = _choice(data.get("difficulty"), DIFFICULTIES, "difficulty")
    grid, _ = _generate_arrow_maze(puzzle_id, difficulty)
    size = ARROW_SETTINGS[difficulty]["size"]
    path = _validate_arrow_path(data.get("path"), grid, size)
    solution = _arrow_solution(grid, size, path[-1])
    if not solution or len(solution) < 2:
        raise puzzle_games.PuzzleError("已经到达终点", "ALREADY_COMPLETED")
    return {"next_index": solution[1], "remaining_steps": len(solution) - 1}


def submit_arrow_maze(user, data):
    puzzle_id = str(data.get("puzzle_id") or "")
    difficulty = _choice(data.get("difficulty"), DIFFICULTIES, "difficulty")
    grid, solution = _generate_arrow_maze(puzzle_id, difficulty)
    size = ARROW_SETTINGS[difficulty]["size"]
    path = _validate_arrow_path(data.get("path"), grid, size)
    run = puzzle_games._owned_run(user, data.get("run_id"), "arrow_maze", puzzle_id, allow_completed=True)
    if user and not run:
        run = storage.get_playing_run(user["id"], "arrow_maze", puzzle_id)
    if run:
        original = puzzle_games._idempotent_result(run)
        if original:
            return original
    if path[-1] != size * size - 1:
        return {"correct": False, "status": "playing", "current_index": path[-1]}
    elapsed = max(run["elapsed_seconds"] if run else 0, puzzle_games._elapsed(data))
    hints = max(run["hints_used"] if run else 0, _integer(data, "hints_used", 0, 1000, 0))
    mistakes = max(run["mistakes"] if run else 0, _integer(data, "mistakes", 0, 100000, 0))
    steps = len(path) - 1
    optimal = len(solution) - 1
    score = max(100, 2200 - steps * 45 - elapsed - hints * 100 - mistakes * 25)
    stars = 3 if steps <= optimal and hints == 0 else 2 if steps <= optimal + 2 else 1
    result = {
        "score": score,
        "stars": stars,
        "elapsed_seconds": elapsed,
        "moves": steps,
        "optimal_steps": optimal,
        "hints_used": hints,
        "mistakes": mistakes,
        "is_new_best": bool(user and puzzle_games._is_new_best(user["id"], "arrow_maze", score)),
    }
    level_order = _level_order_from_puzzle_id(puzzle_id, "arrow_maze", difficulty)
    if level_order:
        result["level_order"] = level_order
        result["next_level_order"] = level_order + 1 if level_order < EXTRA_LEVEL_COUNT else None
    if run:
        completed, saved_run = storage.complete_game_run(
            run["id"], user["id"], {"path": path, "result": result}, elapsed, hints, mistakes, score, stars
        )
        if not completed:
            return puzzle_games._idempotent_result(saved_run) or {"correct": True, "status": "completed", "result": result}
    return {"correct": True, "status": "completed", "result": result}
