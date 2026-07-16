"""Deterministic, offline-safe seed content for the puzzle game APIs."""

import json
import random


SUDOKU_BASES = {
    "easy": (
        "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
        "534678912672195348198342567859761423426853791713924856961537284287419635345286179",
    ),
    "medium": (
        "000260701680070090190004500820100040004602900050003028009300074040050036703018000",
        "435269781682571493197834562826195347374682915951743628519326874248957136763418259",
    ),
    "hard": (
        "000000907000420180000705026100904000050000040000507009920108000034059000507000000",
        "462831957795426183381795426173984265659312748248567319926178534834259671517643892",
    ),
}


IDIOMS = [
    ("画龙点睛", "比喻在关键处加上一笔，使内容更加生动。", "basic"),
    ("一心一意", "形容心思专一，没有别的念头。", "basic"),
    ("待人接物", "指跟别人交往相处。", "basic"),
    ("掩人耳目", "比喻用假象迷惑别人。", "basic"),
    ("牛刀小试", "比喻有大本领的人先在小事上略展才能。", "basic"),
    ("自强不息", "指自己努力向上，永不懈怠。", "basic"),
    ("实事求是", "从实际情况出发，正确认识和解决问题。", "basic"),
    ("虎头蛇尾", "比喻开始时声势很大，后来劲头很小。", "basic"),
    ("鸡鸣狗盗", "指微不足道的本领，也指偷偷摸摸的行为。", "basic"),
    ("守株待兔", "比喻拘泥旧法或妄想不劳而获。", "basic"),
    ("亡羊补牢", "比喻出了问题后及时补救，仍然不晚。", "basic"),
    ("充耳不闻", "塞住耳朵不听，形容有意不听取意见。", "basic"),
    ("掩耳盗铃", "比喻自己欺骗自己。", "basic"),
    ("井底之蛙", "比喻见识狭窄的人。", "basic"),
    ("对牛弹琴", "比喻对不懂道理的人讲高深道理。", "basic"),
    ("狐假虎威", "比喻倚仗别人的势力欺压人。", "basic"),
    ("叶公好龙", "比喻表面爱好，实际上并不真正喜欢。", "basic"),
    ("胸有成竹", "比喻做事前已有成熟的计划。", "basic"),
    ("闻鸡起舞", "比喻有志者及时奋发努力。", "basic"),
    ("滥竽充数", "比喻没有真才实学的人混在行家中充数。", "basic"),
    ("春暖花开", "形容春天气候温暖，百花盛开。", "nature"),
    ("风和日丽", "形容天气晴朗暖和。", "nature"),
    ("山清水秀", "形容山水风景优美。", "nature"),
    ("鸟语花香", "形容春天景色美好。", "nature"),
    ("秋高气爽", "形容秋天天空晴朗，气候凉爽。", "nature"),
    ("秋风落叶", "秋风扫尽落叶，比喻强大力量迅速清除事物。", "nature"),
    ("波澜壮阔", "比喻声势雄壮或规模宏大。", "nature"),
    ("雷厉风行", "形容办事声势猛烈，行动迅速。", "nature"),
    ("草木皆兵", "形容人在惊慌时疑神疑鬼。", "nature"),
    ("电闪雷鸣", "闪电飞光，雷声轰鸣。", "nature"),
    ("层出不穷", "接连不断地出现，没有穷尽。", "nature"),
    ("云开雾散", "比喻疑虑、误会等一下子消除。", "nature"),
    ("草长莺飞", "形容暮春时节生机勃勃的景象。", "nature"),
    ("层峦叠嶂", "形容山峰多而险峻。", "nature"),
    ("百花齐放", "形容百花盛开，丰富多彩。", "nature"),
    ("湖光山色", "湖水的光和山中的景色。", "nature"),
    ("冰天雪地", "形容冰雪漫天盖地，非常寒冷。", "nature"),
    ("海阔天空", "形容天地广阔，也比喻想象或谈论无拘束。", "nature"),
    ("万里无云", "形容天气晴朗，没有一丝云彩。", "nature"),
    ("繁花似锦", "形容美好的景色或事物。", "nature"),
    ("温故知新", "温习旧知识，从而获得新的理解。", "wisdom"),
    ("学而不厌", "学习总感到不满足，形容勤奋好学。", "wisdom"),
    ("举一反三", "从一件事类推而知道许多事情。", "wisdom"),
    ("融会贯通", "把多方面知识融合，得到全面透彻的理解。", "wisdom"),
    ("博古通今", "对古代的事知道很多，也通晓现代事情。", "wisdom"),
    ("孜孜不倦", "勤奋努力，不知疲倦。", "wisdom"),
    ("勤能补拙", "勤奋能够弥补能力上的不足。", "wisdom"),
    ("熟能生巧", "熟练了就能掌握技巧。", "wisdom"),
    ("开卷有益", "读书总有好处。", "wisdom"),
    ("集思广益", "集中众人的智慧，广泛吸收有益意见。", "wisdom"),
    ("深思熟虑", "反复深入细致地考虑。", "wisdom"),
    ("触类旁通", "掌握某一事物规律，进而推知同类事物。", "wisdom"),
    ("见微知著", "见到细微迹象就能知道发展趋势。", "wisdom"),
    ("风雨同舟", "比喻共同经历患难。", "wisdom"),
    ("未雨绸缪", "比喻事先做好准备。", "wisdom"),
    ("防微杜渐", "在错误或坏事刚萌芽时就加以制止。", "wisdom"),
    ("锲而不舍", "不断地雕刻，比喻坚持不懈。", "wisdom"),
    ("持之以恒", "长久坚持下去。", "wisdom"),
    ("精益求精", "已经很好了还要求更加完美。", "wisdom"),
    ("日积月累", "长时间不断积累。", "wisdom"),
]


IDIOM_CATEGORY_NAMES = {
    "basic": ("常用成语", "从高频典故和生活表达开始"),
    "nature": ("自然万象", "在四季山水中完成交叉填字"),
    "wisdom": ("学思智慧", "用经典格言挑战进阶关卡"),
}


def count_sudoku_solutions(puzzle, limit=2):
    board = [int(value) for value in puzzle]
    rows = [set(range(1, 10)) for _ in range(9)]
    columns = [set(range(1, 10)) for _ in range(9)]
    boxes = [set(range(1, 10)) for _ in range(9)]
    for index, value in enumerate(board):
        if not value:
            continue
        row, column = divmod(index, 9)
        box = (row // 3) * 3 + column // 3
        if value not in rows[row] or value not in columns[column] or value not in boxes[box]:
            return 0
        rows[row].remove(value)
        columns[column].remove(value)
        boxes[box].remove(value)

    solutions = 0

    def solve():
        nonlocal solutions
        if solutions >= limit:
            return
        target = None
        candidates = None
        for index, value in enumerate(board):
            if value:
                continue
            row, column = divmod(index, 9)
            box = (row // 3) * 3 + column // 3
            current = rows[row] & columns[column] & boxes[box]
            if not current:
                return
            if candidates is None or len(current) < len(candidates):
                target, candidates = index, current
                if len(candidates) == 1:
                    break
        if target is None:
            solutions += 1
            return
        row, column = divmod(target, 9)
        box = (row // 3) * 3 + column // 3
        for value in tuple(candidates):
            board[target] = value
            rows[row].remove(value)
            columns[column].remove(value)
            boxes[box].remove(value)
            solve()
            boxes[box].add(value)
            columns[column].add(value)
            rows[row].add(value)
            board[target] = 0

    solve()
    return solutions


def sudoku_solution_valid(puzzle, solution):
    if (
        not isinstance(puzzle, str)
        or not isinstance(solution, str)
        or len(puzzle) != 81
        or len(solution) != 81
        or any(value not in "0123456789" for value in puzzle)
        or any(value not in "123456789" for value in solution)
    ):
        return False
    for index, given in enumerate(puzzle):
        if given != "0" and solution[index] != given:
            return False
    expected = set("123456789")
    for row in range(9):
        if set(solution[row * 9 : row * 9 + 9]) != expected:
            return False
    for column in range(9):
        if {solution[row * 9 + column] for row in range(9)} != expected:
            return False
    for box_row in range(3):
        for box_column in range(3):
            values = {
                solution[(box_row * 3 + row) * 9 + box_column * 3 + column]
                for row in range(3)
                for column in range(3)
            }
            if values != expected:
                return False
    return True


def _sudoku_transform(puzzle, solution, difficulty, index):
    rng = random.Random(f"word-game:{difficulty}:{index}")
    digits = list("123456789")
    shuffled = digits[:]
    rng.shuffle(shuffled)
    digit_map = dict(zip(digits, shuffled))
    digit_map["0"] = "0"

    bands = [0, 1, 2]
    stacks = [0, 1, 2]
    rng.shuffle(bands)
    rng.shuffle(stacks)
    row_order = []
    column_order = []
    for band in bands:
        inside = [0, 1, 2]
        rng.shuffle(inside)
        row_order.extend(band * 3 + offset for offset in inside)
    for stack in stacks:
        inside = [0, 1, 2]
        rng.shuffle(inside)
        column_order.extend(stack * 3 + offset for offset in inside)

    def transform(source):
        return "".join(digit_map[source[row * 9 + column]] for row in row_order for column in column_order)

    return transform(puzzle), transform(solution)


def _idiom_layout(index):
    word, definition, category = IDIOMS[index]
    partner_index = None
    shared = None
    for offset in range(1, len(IDIOMS)):
        candidate_index = (index + offset) % len(IDIOMS)
        candidate_word = IDIOMS[candidate_index][0]
        common = next((character for character in word if character in candidate_word), None)
        if common:
            partner_index = candidate_index
            shared = common
            break
    if partner_index is None:
        raise ValueError(f"成语 {word} 没有可交叉的配对")

    partner_word, partner_definition, _ = IDIOMS[partner_index]
    across_row = partner_word.index(shared)
    down_column = word.index(shared)
    values = {}
    for column, character in enumerate(word):
        values[(across_row, column)] = character
    for row, character in enumerate(partner_word):
        values[(row, down_column)] = character

    fixed_position = (across_row, 0)
    cells = []
    solution = {}
    for row, column in sorted(values):
        character = values[(row, column)]
        cell = {"row": row, "column": column, "type": "fixed" if (row, column) == fixed_position else "input"}
        if cell["type"] == "fixed":
            cell["value"] = character
        cells.append(cell)
        solution[f"{row},{column}"] = character

    entries = [
        {
            "id": "entry-1",
            "direction": "across",
            "start": {"row": across_row, "column": 0},
            "length": 4,
            "clue": definition,
            "pinyin_hint": "· · · ·",
        },
        {
            "id": "entry-2",
            "direction": "down",
            "start": {"row": 0, "column": down_column},
            "length": 4,
            "clue": partner_definition,
            "pinyin_hint": "· · · ·",
        },
    ]
    input_characters = [solution[f"{cell['row']},{cell['column']}"] for cell in cells if cell["type"] == "input"]
    distractors = list("天地人心山水风月春秋")
    rng = random.Random(f"idiom-bank:{index}")
    rng.shuffle(distractors)
    character_bank = input_characters + distractors[:4]
    rng.shuffle(character_bank)
    return {
        "category": category,
        "layout": {"cells": cells, "character_bank": character_bank},
        "entries": entries,
        "solution": solution,
    }


def seed_puzzle_catalogs(connection):
    for difficulty, (puzzle, solution) in SUDOKU_BASES.items():
        if count_sudoku_solutions(puzzle) != 1 or not sudoku_solution_valid(puzzle, solution):
            raise ValueError(f"{difficulty} 数独基础题不是唯一解")
        for index in range(100):
            transformed_puzzle, transformed_solution = _sudoku_transform(
                puzzle, solution, difficulty, index
            )
            connection.execute(
                """
                INSERT INTO sudoku_puzzles (id, difficulty, puzzle, solution)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    difficulty = excluded.difficulty,
                    puzzle = excluded.puzzle,
                    solution = excluded.solution,
                    is_active = 1
                """,
                (
                    f"sdk-{difficulty}-{index + 1:06d}",
                    difficulty,
                    transformed_puzzle,
                    transformed_solution,
                ),
            )

    category_orders = {key: 0 for key in IDIOM_CATEGORY_NAMES}
    for index, (word, _, category) in enumerate(IDIOMS):
        if len(word) != 4:
            raise ValueError(f"只允许四字成语: {word}")
        category_orders[category] += 1
        category_order = category_orders[category]
        difficulty = "easy" if category_order <= 7 else "medium" if category_order <= 14 else "hard"
        layout = _idiom_layout(index)
        connection.execute(
            """
            INSERT INTO idiom_puzzles (
                id, level_order, category, difficulty, title, size,
                layout_json, clues_json, solution_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                level_order = excluded.level_order,
                category = excluded.category,
                difficulty = excluded.difficulty,
                title = excluded.title,
                size = excluded.size,
                layout_json = excluded.layout_json,
                clues_json = excluded.clues_json,
                solution_json = excluded.solution_json,
                is_daily_enabled = 1,
                is_active = 1
            """,
            (
                f"idiom-{index + 1:03d}",
                index + 1,
                category,
                difficulty,
                f"{IDIOM_CATEGORY_NAMES[category][0]} {category_order}",
                4,
                json.dumps(layout["layout"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(layout["entries"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(layout["solution"], ensure_ascii=False, separators=(",", ":")),
            ),
        )
