# 益智游戏平台后台联调说明

实现版本：`puzzle-api-v1`

## 启动与初始化

后台启动时会幂等创建新表并补齐内置题库，不修改 `users.game_state`。也可以手动运行：

```bash
cd backend
../.venv/bin/python scripts/seed_puzzles.py --verify
```

题库范围：

- 内置数独：`easy`、`medium`、`hard` 各 100 道，共 300 道；由唯一解基础题做保持唯一解的行列和数字置换。
- 内置成语：6 个分类、每类 20 关，共 120 个双词交叉关卡。
- 外部冻结题库：额外 3000 道数独和 1000 个无重复答案的成语交叉关卡；不会在服务启动时自动导入。
- 记忆翻牌：12 个主题；8、10、15 对三种难度，小程序共 45 个练习关卡。

首次部署外部题库时，先备份 SQLite，再显式运行：

```bash
cd backend
../.venv/bin/python scripts/import_external_puzzle_banks.py
```

成功后数独共 3300 道（每种难度 1100 道），成语共 1120 关。导入过程会全量验证、
按题面/答案去重并在一个事务内完成；重复运行不会覆盖已发布内容。来源、固定版本、
许可证和复现方式见 `data/README.md`。

## 认证

益智游戏接口同时兼容网页 Cookie 会话和小程序 Bearer Token：

```http
# 网页端：登录成功后由浏览器携带 Flask session Cookie
POST /api/auth/register
POST /api/auth/login

# 小程序端：登录成功后携带返回的 Token
POST /api/mobile/auth/register
POST /api/mobile/auth/login
Authorization: Bearer <token>
```

网页端跨域调用时必须允许携带 credentials。如果请求已带 Bearer 头，后端会优先按 Token
解析；过期或伪造的 Token 会返回 `401 INVALID_TOKEN`，不会再回退使用同一请求中的 Cookie。
因此网页端不要额外携带过期 Bearer Token。

不在仓库中保存固定测试密码。联调账号可通过注册接口创建。

## 接口文件

完整路径、参数和请求/响应示例见 `openapi-puzzle-games.yaml`。所有新错误都包含：

```json
{
  "error": "用户可读错误信息",
  "code": "MACHINE_READABLE_CODE"
}
```

主要错误码：

- `AUTH_REQUIRED`
- `INVALID_TOKEN`
- `INVALID_JSON`
- `REQUEST_TOO_LARGE`
- `INVALID_PARAMETER`
- `PUZZLE_NOT_FOUND`
- `PUZZLE_CATALOG_EMPTY`
- `RUN_ID_REQUIRED`
- `RUN_NOT_FOUND`
- `RUN_ALREADY_COMPLETED`
- `RUN_STATE_CONFLICT`
- `PROGRESS_REGRESSION`
- `INVALID_GRID`
- `INVALID_NOTES`
- `SUDOKU_GIVEN_CHANGED`
- `IDIOM_FIXED_CHANGED`
- `INVALID_MATCHES`
- `INVALID_PATH`
- `DUPLICATE_PATH`
- `WORD_NOT_FOUND`
- `PUZZLE_GENERATION_FAILED`
- `HINT_LIMIT_REACHED`
- `NO_HINT_AVAILABLE`
- `LEVEL_LOCKED`
- `INTERNAL_ERROR`

## 字阵寻踪

字阵寻踪使用成语题库生成确定性字符网格，支持 `daily` 和 `practice` 两种模式。当前主题为：

- `classic`：成语万花筒
- `nature`：自然万象
- `animals`：动物世界
- `character`：品格修养
- `emotion`：心情百态

难度递增为 `easy` 6×6/4 词、`medium` 7×7/6 词、`hard` 8×8/8 词。

### `GET /api/word-search/themes`

公开接口，返回 `themes` 和 `difficulties` 数组。主题项包含 `key`、`title`、`description`；
难度项包含 `key`、`rows`、`columns`、`word_count`。

### `GET /api/word-search/board`

查询参数：

- `mode`：必填，`daily` 或 `practice`。
- `difficulty`：必填，`easy`、`medium` 或 `hard`。
- `theme`：可选，默认 `classic`。
- `board_id`：可选，用于恢复指定字阵；其签名内容必须与前三个参数一致。
- `fresh`：可选；练习模式传 `1` 强制开始新字阵。登录用户相同难度、主题的旧未完成局会标记为 `abandoned`；每日模式忽略此参数。

典型响应：

```json
{
  "board_id": "ws1.practice.easy.classic.a1b2c3d4e5f60708.1234567890abcdef1234",
  "mode": "practice",
  "puzzle_date": null,
  "difficulty": "easy",
  "theme": "classic",
  "theme_title": "成语万花筒",
  "rows": 6,
  "columns": 6,
  "word_count": 4,
  "grid": [["天", "海", "…"], ["…"]],
  "entries": [
    {"id": "entry-1", "clue": "用来描述某种情形的线索", "length": 4}
  ],
  "run_id": "run_f9c4a03e",
  "saved_state": {
    "found_entry_ids": ["entry-1"],
    "found_paths": [[
      {"row": 0, "column": 1},
      {"row": 1, "column": 1},
      {"row": 2, "column": 1},
      {"row": 3, "column": 1}
    ]],
    "elapsed_seconds": 28,
    "mistakes": 1
  }
}
```

示例中 `grid` 为省略展示，实际响应始终是 `rows`×`columns` 的完整矩形。`entries`
只公开 `id`、线索和长度，不包含成语原文、答案或放置路径。游客的 `run_id` 和
`saved_state` 均为 `null`。

`board_id` 带 HMAC 签名，后端在每次保存和提交时都会校验签名并重建原题，
客户端应将它视为不透明字符串。签名密钥优先读取 `WORD_SEARCH_BOARD_SECRET`，其次使用
`WORD_GAME_SECRET_KEY`。生产环境需设置稳定密钥；更换密钥会使已发放的 `board_id` 失效。

`daily` 按服务端上海时区日期、难度和主题固定。登录用户请求 `practice` 时，会自动恢复相同
难度和主题的最新未完成运行记录。游客需将 `board_id`、已找路径、用时和错误数存在本地，
恢复时用 `board_id` 查询参数重新获取同一字阵。练习模式需要主动换题时传 `fresh=1`；登录
用户会先关闭同主题的旧未完成 run，再创建新题与新 run。

### `POST /api/word-search/save`

仅 Cookie 或 Bearer 已登录用户可用；游客调用返回 `401 AUTH_REQUIRED`。

```json
{
  "run_id": "run_f9c4a03e",
  "board_id": "ws1.practice.easy.classic.a1b2c3d4e5f60708.1234567890abcdef1234",
  "found_paths": [[
    {"row": 0, "column": 1},
    {"row": 1, "column": 1},
    {"row": 2, "column": 1},
    {"row": 3, "column": 1}
  ]],
  "elapsed_seconds": 28,
  "mistakes": 1
}
```

服务端只信任经签名题目验证通过的 `found_paths`，不接受客户端传入 `found_entry_ids`
作为进度依据。已确认词条不能减少，`elapsed_seconds` 和 `mistakes` 也不能小于已保存值，
否则返回 `PROGRESS_REGRESSION`。成功返回 `saved`、`run_id` 和 `updated_at`。
`save` 中如果出现格式合法但不属于本题的路径，也会返回 422，但该接口使用通用
`{"error": "...", "code": "WORD_NOT_FOUND"}` 结构；它与下面 `submit` 的 422 游戏结果不同。

### `POST /api/word-search/submit`

游客和登录用户均可调用。客户端可增量提交本次的 `path`，也可用 `found_paths` 传入已找到的
全部路径；两者同时传入时，`path` 会追加到 `found_paths`。坐标从 0 开始，路径必须在水平、
垂直或 45° 对角线上连续且无重复格；正向和反向都会被接受。

```json
{
  "run_id": "run_f9c4a03e",
  "board_id": "ws1.practice.easy.classic.a1b2c3d4e5f60708.1234567890abcdef1234",
  "path": [
    {"row": 0, "column": 1},
    {"row": 1, "column": 1},
    {"row": 2, "column": 1},
    {"row": 3, "column": 1}
  ],
  "found_paths": [],
  "elapsed_seconds": 28,
  "mistakes": 0
}
```

找到目标但尚未找齐时返回 `200`：

```json
{
  "correct": true,
  "status": "playing",
  "found_entry_ids": ["entry-1"],
  "found_count": 1,
  "remaining_count": 3
}
```

所有词条找齐时返回 `200` 和 `status: "completed"`，`result` 包含 `score`、`stars`、
`elapsed_seconds`、`mistakes`、`found_count` 和 `is_new_best`。登录用户的完成提交幂等，
再次提交会返回首次完成的原结果。

坐标格式合法、但路径不是本题目标词时返回 **422 业务响应**：

```json
{
  "correct": false,
  "status": "incorrect",
  "code": "WORD_NOT_FOUND",
  "mistakes": 2
}
```

该 422 响应不是通用 `Error` 结构，且不包含答案或正确路径。前端请求层必须保留响应体，
将 422 当作可渲染的游戏结果。路径不连续、越界、重复格或重复提交同一词条等结构/状态错误
仍返回 `400 Error`。登录用户的错误选择会在服务端累加 `mistakes`；游客须自行保留返回值。

游客没有云端运行记录，因此每次请求必须携带同一 `board_id`，并在本地保留累积的
`found_paths`、`elapsed_seconds` 和 `mistakes`。服务端返回的 `found_entry_ids` 用于界面标记，
不能替代下一次提交所需的路径坐标。

## 自动化验证

```bash
cd backend
../.venv/bin/python -m unittest -v test_puzzle_api.py test_external_puzzle_import.py test_word_search_api.py
```

测试覆盖游客读取、登录云存档、每日题固定、提示恢复、错误提交、成语解锁、翻牌配对校验、后端计分、重复提交幂等，以及外部题库的事务回滚、去重和不可变性。
字阵测试另外覆盖签名 `board_id` 防伪造、正反向路径、422 不泄题响应、云端恢复、完成幂等和禁止伪造词条 ID。

游客成语目录默认只标记每个分类第一关为已解锁；游客完成状态由小程序本地保存和覆盖，后台允许游客读取任意有效普通关卡。登录用户仍由后台严格校验关卡顺序。

数独和成语存档允许擦除或改写普通输入格，只禁止修改数独给定格和成语固定格。`elapsed_seconds`、`mistakes` 以及翻牌已匹配位置仍不能回退。

## 诗词大会、推箱子与箭头迷宫

三款扩展游戏继续使用 `game_runs`、Bearer Token、每日题映射和 422 业务结果约定：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/poetry/quiz` | 获取每日或练习题组 |
| POST | `/api/poetry/save` | 保存题号、答对数和用时 |
| POST | `/api/poetry/submit` | 提交当前选择并取得下一题或结算 |
| GET | `/api/sokoban/board` | 获取确定性推箱子关卡 |
| POST | `/api/sokoban/save` | 保存可回放的 `UDLR` 移动记录 |
| POST | `/api/sokoban/submit` | 服务端重放移动并验证所有箱子归位 |
| GET | `/api/arrow-maze/board` | 获取箭头跳格迷宫 |
| POST | `/api/arrow-maze/save` | 保存可回退路径 |
| POST | `/api/arrow-maze/hint` | 返回当前位置最短路线的下一格 |
| POST | `/api/arrow-maze/submit` | 验证路径方向和出口并结算 |

三个 GET 接口均接受 `mode=daily|practice`、`difficulty=easy|medium|hard`，自由练习可加
`fresh=1` 换题。游客的 `run_id`、`saved_state` 为 `null`，由小程序保存题面和进度；登录用户
在每次重新进入时恢复未完成运行。推箱子的移动记录和箭头迷宫路径允许因撤回操作而缩短，
但 `elapsed_seconds`、`hints_used` 和 `mistakes` 不能回退。

诗词题库由 38 首内置基础作品和 `backend/data/poetry_bank.json` 的 1445 首标准化作品合并
去重，共 1468 首。简单、中等、困难题池为逐级包含关系，规模分别为 427、861、1468 首；
每局题量分别为 12、20、30。每日题使用固定乱序表按天步进，相邻日期无重复，并返回
`catalog_size` 与 `rotation_days` 供客户端展示；自由练习使用独立随机题组。
