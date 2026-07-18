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
    ("百折不挠", "无论受到多少挫折都不退缩。", "growth"),
    ("坚持不懈", "坚持到底，一点也不松懈。", "growth"),
    ("勇往直前", "勇敢地一直向前进。", "growth"),
    ("迎难而上", "面对困难主动向前。", "growth"),
    ("全力以赴", "把全部力量都投入进去。", "growth"),
    ("脚踏实地", "做事踏实认真，不浮躁。", "growth"),
    ("厚积薄发", "经过充分积累后稳步发挥。", "growth"),
    ("水滴石穿", "比喻坚持不懈就能取得成功。", "growth"),
    ("绳锯木断", "比喻力量虽小，坚持也能成功。", "growth"),
    ("铁杵成针", "比喻只要有恒心就能成功。", "growth"),
    ("志存高远", "追求远大的理想和目标。", "growth"),
    ("发奋图强", "振作精神，努力谋求强盛。", "growth"),
    ("奋发有为", "精神振作，努力有所作为。", "growth"),
    ("乘风破浪", "比喻排除困难，奋勇前进。", "growth"),
    ("一往无前", "勇猛向前，不受阻挡。", "growth"),
    ("独当一面", "能够独立承担一方面的工作。", "growth"),
    ("自力更生", "依靠自己的力量改变处境。", "growth"),
    ("力争上游", "努力奋斗，争取先进。", "growth"),
    ("争分夺秒", "充分利用每一点时间。", "growth"),
    ("分秒必争", "一分一秒也不放过。", "growth"),
    ("推心置腹", "真心待人，毫无保留。", "relations"),
    ("肝胆相照", "比喻彼此真诚相见。", "relations"),
    ("情同手足", "感情深厚得像兄弟一样。", "relations"),
    ("雪中送炭", "在别人急需时给予帮助。", "relations"),
    ("同甘共苦", "共同享受幸福，共同承担困难。", "relations"),
    ("和衷共济", "同心协力克服困难。", "relations"),
    ("守望相助", "为了共同目标互相帮助。", "relations"),
    ("礼尚往来", "礼节上讲究有来有往。", "relations"),
    ("宾至如归", "客人到这里像回到自己家一样。", "relations"),
    ("将心比心", "设身处地替别人着想。", "relations"),
    ("心平气和", "心情平静，态度温和。", "relations"),
    ("以诚相待", "用真诚的态度对待别人。", "relations"),
    ("开诚布公", "诚意待人，坦白无私。", "relations"),
    ("宽以待人", "用宽容的态度对待别人。", "relations"),
    ("善解人意", "善于理解别人的心意。", "relations"),
    ("相敬如宾", "彼此尊敬得像对待客人一样。", "relations"),
    ("不计前嫌", "不再计较过去的嫌隙。", "relations"),
    ("一诺千金", "形容说话极有信用。", "relations"),
    ("言而有信", "说话算数，讲信用。", "relations"),
    ("成人之美", "帮助别人实现好事。", "relations"),
    ("卧薪尝胆", "形容刻苦自励，立志雪耻图强。", "stories"),
    ("破釜沉舟", "比喻下定决心，不留退路。", "stories"),
    ("三顾茅庐", "比喻诚心诚意地邀请人才。", "stories"),
    ("围魏救赵", "比喻袭击敌人后方以解除正面危机。", "stories"),
    ("完璧归赵", "比喻把原物完整地归还本人。", "stories"),
    ("纸上谈兵", "比喻空谈理论，不能解决实际问题。", "stories"),
    ("指鹿为马", "比喻故意颠倒黑白，混淆是非。", "stories"),
    ("四面楚歌", "比喻陷入孤立无援的境地。", "stories"),
    ("草船借箭", "比喻巧妙借助他人力量达到目的。", "stories"),
    ("望梅止渴", "比喻用空想安慰自己。", "stories"),
    ("程门立雪", "形容尊师重道，恭敬求教。", "stories"),
    ("凿壁偷光", "形容家贫而刻苦读书。", "stories"),
    ("囊萤映雪", "形容在艰苦条件下勤奋学习。", "stories"),
    ("韦编三绝", "形容读书勤奋刻苦。", "stories"),
    ("东山再起", "比喻失势后重新恢复地位。", "stories"),
    ("背水一战", "比喻在绝境中作最后决战。", "stories"),
    ("退避三舍", "比喻主动退让，不与人相争。", "stories"),
    ("毛遂自荐", "比喻自己推荐自己。", "stories"),
    ("老马识途", "比喻有经验的人熟悉情况。", "stories"),
    ("图穷匕见", "比喻事情发展到最后显露真相。", "stories"),
]


IDIOM_CATEGORY_NAMES = {
    "basic": ("常用成语", "从高频典故和生活表达开始"),
    "nature": ("自然万象", "在四季山水中完成交叉填字"),
    "wisdom": ("学思智慧", "用经典格言挑战进阶关卡"),
    "growth": ("奋进成长", "在坚持与行动中积累前进力量"),
    "relations": ("人情相处", "从待人接物中读懂真诚与分寸"),
    "stories": ("典故纵横", "沿着历史故事解锁成语来历"),
    "curated-01": ("词库精选一", "从高频成语开始，逐步提升填字难度"),
    "curated-02": ("词库精选二", "精选常用表达，完成一百道递进关卡"),
    "curated-03": ("词库精选三", "扩展成语储备，在交叉线索中稳步进阶"),
    "curated-04": ("词库精选四", "结合释义与拼音，挑战更丰富的词汇"),
    "curated-05": ("词库精选五", "由易到难掌握更多常见成语"),
    "curated-06": ("词库精选六", "继续积累词汇，训练联想与辨析能力"),
    "curated-07": ("词库精选七", "进入进阶题组，寻找更隐蔽的交叉点"),
    "curated-08": ("词库精选八", "挑战中高难释义与相近表达"),
    "curated-09": ("词库精选九", "在复杂线索中巩固成语知识"),
    "curated-10": ("词库精选十", "完成终章挑战，检验综合词汇能力"),
}

# Published puzzle ids are immutable. Each boundary freezes the partner search
# pool for that release, so appending a later content batch cannot change an
# existing idiom-xxx layout. Add a new boundary when a new built-in batch is
# appended; never edit or remove an earlier value.
IDIOM_LAYOUT_COHORT_ENDS = (60, 120)
IDIOM_LAYOUT_VERSION = 2
IDIOM_ENTRY_COUNTS = {"easy": 2, "medium": 3, "hard": 4}
IDIOM_BRIDGE_ENTRIES = [
    ("威风凛凛", "形容声势或气派令人敬畏。"),
    ("气冲斗牛", "形容气势或怒气直冲天际。"),
    ("通情达理", "形容说话做事合乎情理。"),
]


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
    cohort_end = next((end for end in IDIOM_LAYOUT_COHORT_ENDS if index < end), None)
    if cohort_end is None or cohort_end > len(IDIOMS):
        raise ValueError(f"成语 {word} 未配置稳定的布局批次")
    partner_index = None
    shared = None
    for offset in range(1, cohort_end):
        candidate_index = (index + offset) % cohort_end
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


def _entry_word(entry, solution):
    row = int(entry["start"]["row"])
    column = int(entry["start"]["column"])
    values = []
    for offset in range(int(entry["length"])):
        current_row = row + (offset if entry["direction"] == "down" else 0)
        current_column = column + (offset if entry["direction"] == "across" else 0)
        value = solution.get(f"{current_row},{current_column}")
        if not isinstance(value, str) or len(value) != 1:
            return ""
        values.append(value)
    return "".join(values)


def _crossword_layout(primary, candidates, entry_count, seed):
    """Build a deterministic, connected crossword with 2-4 four-character idioms."""
    primary_word, primary_clue = primary
    if len(primary_word) != 4:
        raise ValueError(f"只允许四字成语: {primary_word}")

    rng = random.Random(f"idiom-crossword-v{IDIOM_LAYOUT_VERSION}:{seed}")
    ordered = []
    seen = {primary_word}
    for word, clue in candidates:
        if len(word) == 4 and word not in seen:
            seen.add(word)
            ordered.append((word, clue))
    rng.shuffle(ordered)

    placed = [
        {
            "word": primary_word,
            "clue": primary_clue,
            "direction": "across",
            "row": 0,
            "column": 0,
        }
    ]
    values = {(0, column): character for column, character in enumerate(primary_word)}
    directions = {(0, column): {"across"} for column in range(4)}

    def placement_options(word, clue, candidate_order, current_placed, current_values, current_directions):
        options = []
        for anchor_order, anchor in enumerate(current_placed):
            direction = "down" if anchor["direction"] == "across" else "across"
            for anchor_offset, anchor_character in enumerate(anchor["word"]):
                for word_offset, character in enumerate(word):
                    if character != anchor_character:
                        continue
                    crossing_row = anchor["row"] + (
                        anchor_offset if anchor["direction"] == "down" else 0
                    )
                    crossing_column = anchor["column"] + (
                        anchor_offset if anchor["direction"] == "across" else 0
                    )
                    row = crossing_row - (word_offset if direction == "down" else 0)
                    column = crossing_column - (word_offset if direction == "across" else 0)
                    cells = []
                    intersections = 0
                    valid = True
                    for offset, value in enumerate(word):
                        position = (
                            row + (offset if direction == "down" else 0),
                            column + (offset if direction == "across" else 0),
                        )
                        existing = current_values.get(position)
                        if existing is not None:
                            if existing != value or direction in current_directions[position]:
                                valid = False
                                break
                            intersections += 1
                        cells.append((position, value))
                    if not valid or intersections == 0:
                        continue
                    combined = set(current_values) | {position for position, _ in cells}
                    rows = [position[0] for position in combined]
                    columns = [position[1] for position in combined]
                    height = max(rows) - min(rows) + 1
                    width = max(columns) - min(columns) + 1
                    score = (
                        max(height, width),
                        height * width,
                        -intersections,
                        candidate_order,
                        anchor_order,
                        row,
                        column,
                    )
                    options.append(
                        (
                            score,
                            {
                                "word": word,
                                "clue": clue,
                                "direction": direction,
                                "row": row,
                                "column": column,
                            },
                            cells,
                        )
                    )
        return options

    def search(current_placed, current_values, current_directions):
        if len(current_placed) >= entry_count:
            return current_placed, current_values, current_directions
        options = []
        used_words = {entry["word"] for entry in current_placed}
        for candidate_order, (word, clue) in enumerate(ordered):
            if word in used_words:
                continue
            options.extend(
                placement_options(
                    word,
                    clue,
                    candidate_order,
                    current_placed,
                    current_values,
                    current_directions,
                )
            )
        options.sort(key=lambda item: item[0])
        # Compact options are tried first. The cap prevents a very large custom
        # catalog from causing exponential startup time while retaining ample
        # alternatives for four-entry layouts.
        for _, entry, cells in options[:600]:
            next_placed = current_placed + [entry]
            next_values = dict(current_values)
            next_directions = {
                position: set(value) for position, value in current_directions.items()
            }
            for position, value in cells:
                next_values[position] = value
                next_directions.setdefault(position, set()).add(entry["direction"])
            result = search(next_placed, next_values, next_directions)
            if result:
                return result
        return None

    result = search(placed, values, directions)
    if not result:
        raise ValueError(f"成语 {primary_word} 无法生成 {entry_count} 条交叉布局")
    placed, values, directions = result

    min_row = min(row for row, _ in values)
    max_row = max(row for row, _ in values)
    min_column = min(column for _, column in values)
    max_column = max(column for _, column in values)
    height = max_row - min_row + 1
    width = max_column - min_column + 1
    size = max(height, width)
    row_padding = (size - height) // 2
    column_padding = (size - width) // 2

    normalized_values = {
        (row - min_row + row_padding, column - min_column + column_padding): value
        for (row, column), value in values.items()
    }
    entries = []
    for entry_index, entry in enumerate(placed, start=1):
        entries.append(
            {
                "id": f"entry-{entry_index}",
                "direction": entry["direction"],
                "start": {
                    "row": entry["row"] - min_row + row_padding,
                    "column": entry["column"] - min_column + column_padding,
                },
                "length": 4,
                "clue": entry["clue"],
                "pinyin_hint": "· · · ·",
            }
        )

    fixed_position = (
        entries[0]["start"]["row"],
        entries[0]["start"]["column"],
    )
    cells = []
    solution = {}
    for row, column in sorted(normalized_values):
        value = normalized_values[(row, column)]
        cell = {
            "row": row,
            "column": column,
            "type": "fixed" if (row, column) == fixed_position else "input",
        }
        if cell["type"] == "fixed":
            cell["value"] = value
        cells.append(cell)
        solution[f"{row},{column}"] = value

    input_characters = [
        solution[f"{cell['row']},{cell['column']}"]
        for cell in cells
        if cell["type"] == "input"
    ]
    distractors = [value for value in "天地人心山水风月春秋云海日夜" if value not in input_characters]
    rng.shuffle(distractors)
    character_bank = input_characters + distractors[:4]
    rng.shuffle(character_bank)
    return {
        "size": size,
        "layout": {"cells": cells, "character_bank": character_bank},
        "entries": entries,
        "solution": solution,
    }


def upgrade_idiom_layouts(connection):
    """Upgrade stored layouts without changing ids, titles, ordering or progress."""
    rows = connection.execute(
        """
        SELECT id, category, difficulty, size, layout_json, clues_json,
               solution_json, layout_version
        FROM idiom_puzzles
        WHERE is_active = 1
        ORDER BY level_order, id
        """
    ).fetchall()
    sources = []
    row_sources = {}
    for row in rows:
        try:
            clues = json.loads(row["clues_json"])
            solution = json.loads(row["solution_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        extracted = []
        for entry in clues:
            word = _entry_word(entry, solution)
            if len(word) == 4:
                source = (word, str(entry.get("clue", "根据释义填写成语")))
                extracted.append(source)
                sources.append((row["category"], *source))
        if extracted:
            row_sources[row["id"]] = extracted

    # A few valid bridge idioms connect otherwise isolated pairs in the
    # built-in catalog, so every medium/hard target can form one connected
    # crossword instead of falling back to separate word islands.
    sources.extend(("__bridge__", word, clue) for word, clue in IDIOM_BRIDGE_ENTRIES)

    for row in rows:
        if int(row["layout_version"] or 1) >= IDIOM_LAYOUT_VERSION:
            continue
        entry_count = IDIOM_ENTRY_COUNTS.get(row["difficulty"], 2)
        primary_sources = row_sources.get(row["id"], [])
        if not primary_sources:
            continue
        if entry_count == 2:
            connection.execute(
                "UPDATE idiom_puzzles SET layout_version = ? WHERE id = ?",
                (IDIOM_LAYOUT_VERSION, row["id"]),
            )
            continue
        same_category = [
            (word, clue)
            for category, word, clue in sources
            if category == row["category"] and word != primary_sources[0][0]
        ]
        other_categories = [
            (word, clue)
            for category, word, clue in sources
            if category != row["category"] and word != primary_sources[0][0]
        ]
        expanded = _crossword_layout(
            primary_sources[0],
            same_category + other_categories,
            entry_count,
            row["id"],
        )
        connection.execute(
            """
            UPDATE idiom_puzzles
            SET size = ?, layout_json = ?, clues_json = ?, solution_json = ?,
                layout_version = ?
            WHERE id = ?
            """,
            (
                expanded["size"],
                json.dumps(expanded["layout"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(expanded["entries"], ensure_ascii=False, separators=(",", ":")),
                json.dumps(expanded["solution"], ensure_ascii=False, separators=(",", ":")),
                IDIOM_LAYOUT_VERSION,
                row["id"],
            ),
        )


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
                ON CONFLICT(id) DO NOTHING
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
            ON CONFLICT(id) DO NOTHING
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
    upgrade_idiom_layouts(connection)
