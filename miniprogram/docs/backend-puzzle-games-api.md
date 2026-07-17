# 益智游戏平台后端开发与 API 对接文档

> 版本：v1.0
> 对接范围：每日数独、成语填字、记忆翻牌、游戏大厅汇总
> 现有系统：Flask + SQLite + Bearer Token
> API Base：`/api`

## 1. 目标

在现有猜词游戏后端上增加三个独立益智游戏，并向微信小程序提供统一的大厅状态、题目获取、进度保存、提示、提交和成绩接口。

本期需要实现：

1. 游戏大厅汇总接口。
2. 每日数独：每日题、自由练习、存档、提示、提交。
3. 成语填字：关卡目录、每日题、关卡题、存档、提示、提交。
4. 记忆翻牌：每日牌面、自由练习、存档、完成记录。
5. 登录用户的云端进度、最好成绩和重复提交保护。
6. 游客可以获取题目和校验结果，但游客进度由小程序本地保存。

本期不包含：

- 排行榜。
- 多人对战。
- 道具付费和皮肤商城。
- 推送通知。
- AI 在线生成题目。

## 2. 与现有后端的兼容要求

现有后端已经具备以下能力，新增接口应继续复用：

- `Authorization: Bearer <token>` 认证。
- `get_current_user()` 获取可选登录用户。
- SQLite 数据库和 `storage.init_db()` 建表方式。
- 成功响应直接返回 JSON 对象。
- 失败响应使用 `{ "error": "错误信息" }`。
- 登录失效返回 HTTP `401`。

不要把三个新游戏的状态写入现有 `users.game_state`。该字段是猜词游戏专用状态，新游戏应使用独立的通用运行记录表。

## 3. 公共接口约定

### 3.1 请求格式

```http
Content-Type: application/json
Authorization: Bearer <token>
```

Token 对只读题目接口可选，对云存档接口必填。

### 3.2 字段格式

- JSON 字段统一使用 `snake_case`。
- 时间统一返回 ISO 8601 UTC 字符串，例如 `2026-07-16T09:30:00Z`。
- 每日挑战日期由服务端按照 `Asia/Shanghai` 计算，不能信任客户端日期。
- 游戏标识固定为：`word`、`sudoku`、`idiom`、`memory`。
- 游戏模式固定为：`daily`、`practice`、`level`。
- 运行状态固定为：`playing`、`completed`、`abandoned`。
- 难度固定为：`easy`、`medium`、`hard`。

### 3.3 错误响应

```json
{
  "error": "题目不存在",
  "code": "PUZZLE_NOT_FOUND"
}
```

`code` 为新增推荐字段，小程序仍以 `error` 作为用户提示。

| HTTP 状态 | 使用场景 |
|---|---|
| `400` | 参数格式错误、棋盘长度错误、非法字符 |
| `401` | 需要云存档但用户未登录或 Token 失效 |
| `403` | 关卡未解锁、提示次数已用完 |
| `404` | 题目、关卡或运行记录不存在 |
| `409` | 运行记录状态冲突，例如已完成后继续保存 |
| `422` | 提交内容完整但答案不正确 |
| `500` | 未处理的服务端错误 |

### 3.4 可选登录规则

| 操作 | 游客 | 登录用户 |
|---|---:|---:|
| 获取题目 | 支持 | 支持 |
| 校验答案 | 支持 | 支持并保存结果 |
| 请求提示 | 支持 | 支持并记录提示次数 |
| 保存中途进度 | 小程序本地保存 | 服务端云存档 |
| 获取历史和最好成绩 | 不支持 | 支持 |

当 GET 题目接口携带有效 Token 时，后台应返回该用户对应题目的未完成存档；未携带 Token 时，`run_id` 和 `saved_state` 返回 `null`。

## 4. 建议数据库结构

### 4.1 通用游戏运行表

```sql
CREATE TABLE IF NOT EXISTS game_runs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    game_key TEXT NOT NULL,
    puzzle_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    difficulty TEXT,
    status TEXT NOT NULL DEFAULT 'playing',
    state_json TEXT,
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    hints_used INTEGER NOT NULL DEFAULT 0,
    mistakes INTEGER NOT NULL DEFAULT 0,
    score INTEGER,
    stars INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_game_runs_user_game
ON game_runs (user_id, game_key, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_game_runs_user_puzzle
ON game_runs (user_id, game_key, puzzle_id, status);
```

要求：

- 每个登录用户、游戏、题目最多保留一个 `playing` 记录。
- 已完成记录再次提交时必须幂等，返回原结果，不能重复累计完成次数。
- `state_json` 只保存游戏运行状态，不保存题库答案。

### 4.2 数独题库表

```sql
CREATE TABLE IF NOT EXISTS sudoku_puzzles (
    id TEXT PRIMARY KEY,
    difficulty TEXT NOT NULL,
    puzzle TEXT NOT NULL,
    solution TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sudoku_difficulty
ON sudoku_puzzles (difficulty, is_active);
```

- `puzzle` 和 `solution` 均为长度 81 的字符串。
- `puzzle` 使用 `0` 表示空格。
- 题目入库前必须验证只有一个解。
- `solution` 绝不能通过题目获取接口返回给客户端。

### 4.3 成语关卡表

```sql
CREATE TABLE IF NOT EXISTS idiom_puzzles (
    id TEXT PRIMARY KEY,
    level_order INTEGER,
    category TEXT,
    difficulty TEXT NOT NULL,
    title TEXT NOT NULL,
    size INTEGER NOT NULL,
    layout_json TEXT NOT NULL,
    clues_json TEXT NOT NULL,
    solution_json TEXT NOT NULL,
    is_daily_enabled INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_idiom_level_order
ON idiom_puzzles (level_order)
WHERE level_order IS NOT NULL;
```

### 4.4 每日题映射表

```sql
CREATE TABLE IF NOT EXISTS daily_puzzles (
    game_key TEXT NOT NULL,
    puzzle_date TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'medium',
    puzzle_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_key, puzzle_date, difficulty)
);
```

服务端第一次请求某日题目时选择并固化题目，之后所有用户必须获得同一题，避免部署或题库顺序变化导致每日题变化。

## 5. 接口总览

| 方法 | 路径 | 登录 | 用途 |
|---|---|---:|---|
| GET | `/api/games/overview` | 可选 | 游戏大厅状态和用户概览 |
| GET | `/api/sudoku/puzzle` | 可选 | 获取每日或练习数独 |
| POST | `/api/sudoku/save` | 必须 | 保存数独中途状态 |
| POST | `/api/sudoku/hint` | 可选 | 获取一个数独提示 |
| POST | `/api/sudoku/submit` | 可选 | 校验并完成数独 |
| GET | `/api/idiom/catalog` | 可选 | 获取成语关卡目录 |
| GET | `/api/idiom/puzzle` | 可选 | 获取每日或指定成语关卡 |
| POST | `/api/idiom/save` | 必须 | 保存成语填字中途状态 |
| POST | `/api/idiom/hint` | 可选 | 揭示一个成语文字 |
| POST | `/api/idiom/submit` | 可选 | 校验并完成成语题 |
| GET | `/api/memory/board` | 可选 | 获取每日或练习翻牌布局 |
| POST | `/api/memory/save` | 必须 | 保存翻牌中途状态 |
| POST | `/api/memory/submit` | 可选 | 保存翻牌完成结果 |

## 6. 游戏大厅接口

### `GET /api/games/overview`

认证可选。登录时返回用户真实进度；游客返回默认进度。

#### 响应

```json
{
  "server_date": "2026-07-16",
  "summary": {
    "available_games": 4,
    "completed_today": 1,
    "total_stars": 36,
    "last_game_key": "sudoku"
  },
  "games": [
    {
      "key": "word",
      "title": "猜词实验室",
      "availability": "available",
      "progress_text": "12 / 780 星",
      "progress_percent": 1.54,
      "best_score": null,
      "daily_completed": false,
      "last_played_at": "2026-07-16T09:12:00Z"
    },
    {
      "key": "sudoku",
      "title": "每日数独",
      "availability": "available",
      "progress_text": "今日未完成",
      "progress_percent": 0,
      "best_score": 920,
      "daily_completed": false,
      "last_played_at": null
    },
    {
      "key": "idiom",
      "title": "成语填字",
      "availability": "available",
      "progress_text": "3 / 120 关",
      "progress_percent": 2.5,
      "best_score": 870,
      "daily_completed": true,
      "last_played_at": "2026-07-16T08:30:00Z"
    },
    {
      "key": "memory",
      "title": "记忆翻牌",
      "availability": "available",
      "progress_text": "最佳 18 步",
      "progress_percent": 0,
      "best_score": 760,
      "daily_completed": false,
      "last_played_at": null
    }
  ]
}
```

`availability` 可取：

- `available`：小程序显示可进入。
- `coming_soon`：显示“即将上线”。
- `maintenance`：显示维护提示，禁止进入。

猜词游戏的 `total_stars` 可直接从现有 `campaign_progress` 汇总；新游戏从 `game_runs` 汇总。

## 7. 每日数独 API

### 7.1 获取题目

### `GET /api/sudoku/puzzle`

#### 查询参数

| 参数 | 必填 | 示例 | 说明 |
|---|---:|---|---|
| `mode` | 是 | `daily` | `daily` 或 `practice` |
| `difficulty` | 是 | `medium` | `easy`、`medium`、`hard` |

#### 响应

```json
{
  "puzzle_id": "sdk-medium-000128",
  "mode": "daily",
  "puzzle_date": "2026-07-16",
  "difficulty": "medium",
  "givens": "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
  "run_id": "run_f9c4a03e",
  "saved_state": {
    "grid": "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
    "notes": {
      "2": [1, 2, 4],
      "3": [2, 6]
    },
    "elapsed_seconds": 84,
    "hints_used": 0,
    "mistakes": 0
  },
  "limits": {
    "max_hints": 3
  }
}
```

游客响应中：

```json
{
  "run_id": null,
  "saved_state": null
}
```

练习模式应尽量避开该用户最近完成的题目。游客练习题可以随机返回。

### 7.2 保存进度

### `POST /api/sudoku/save`

必须登录。

#### 请求

```json
{
  "run_id": "run_f9c4a03e",
  "puzzle_id": "sdk-medium-000128",
  "grid": "534678912600195000098000060800060003400803001700020006060000280000419005000080079",
  "notes": {
    "10": [2, 7],
    "11": [2, 4, 7]
  },
  "elapsed_seconds": 132,
  "mistakes": 1
}
```

#### 响应

```json
{
  "saved": true,
  "run_id": "run_f9c4a03e",
  "updated_at": "2026-07-16T09:32:10Z"
}
```

校验要求：

- `grid` 长度必须为 81。
- 仅允许字符 `0-9`。
- 原始给定数字不能被修改。
- `elapsed_seconds` 不能小于服务端已保存值。
- 已完成运行返回 `409`。

### 7.3 请求提示

### `POST /api/sudoku/hint`

认证可选。

#### 请求

```json
{
  "run_id": "run_f9c4a03e",
  "puzzle_id": "sdk-medium-000128",
  "grid": "534678912600195000098000060800060003400803001700020006060000280000419005000080079"
}
```

#### 响应

```json
{
  "index": 10,
  "row": 1,
  "column": 1,
  "value": 7,
  "hints_used": 1,
  "remaining_hints": 2
}
```

服务端从尚未正确填写的格子中选择一个返回。提示次数达到上限后返回 `403`。

### 7.4 提交答案

### `POST /api/sudoku/submit`

认证可选。

#### 请求

```json
{
  "run_id": "run_f9c4a03e",
  "puzzle_id": "sdk-medium-000128",
  "grid": "534678912672195348198342567859761423426853791713924856961537284287419635345286179",
  "elapsed_seconds": 428,
  "mistakes": 1,
  "hints_used": 0
}
```

#### 完成响应

```json
{
  "correct": true,
  "status": "completed",
  "result": {
    "score": 1052,
    "stars": 3,
    "elapsed_seconds": 428,
    "mistakes": 1,
    "hints_used": 0,
    "is_new_best": true
  }
}
```

#### 答案不完整或错误

```json
{
  "correct": false,
  "status": "incorrect",
  "invalid_cells": [10, 23, 54]
}
```

不要返回完整解答。

## 8. 成语填字 API

### 8.1 获取关卡目录

### `GET /api/idiom/catalog`

认证可选。

#### 响应

```json
{
  "total_stars": 8,
  "max_stars": 180,
  "categories": [
    {
      "id": "basic",
      "name": "常用成语",
      "description": "从日常高频成语开始",
      "completed_levels": 3,
      "total_levels": 20,
      "levels": [
        {
          "id": "idiom-001",
          "order": 1,
          "title": "初露锋芒",
          "difficulty": "easy",
          "unlocked": true,
          "stars": 3,
          "best_score": 920
        }
      ]
    }
  ]
}
```

游客只解锁每个分类的第一关，完成状态由小程序本地覆盖显示；登录用户返回真实云端进度。

### 8.2 获取题目

### `GET /api/idiom/puzzle`

#### 查询参数

每日题：

```text
mode=daily&difficulty=medium
```

关卡题：

```text
mode=level&level_id=idiom-001
```

#### 响应

```json
{
  "puzzle_id": "idiom-001",
  "mode": "level",
  "puzzle_date": null,
  "title": "初露锋芒",
  "difficulty": "easy",
  "size": 5,
  "cells": [
    { "row": 0, "column": 0, "type": "fixed", "value": "画" },
    { "row": 0, "column": 1, "type": "input" },
    { "row": 0, "column": 2, "type": "input" },
    { "row": 0, "column": 3, "type": "input" },
    { "row": 1, "column": 2, "type": "input" }
  ],
  "entries": [
    {
      "id": "entry-1",
      "direction": "across",
      "start": { "row": 0, "column": 0 },
      "length": 4,
      "clue": "比喻在关键处加上一笔，使内容更加生动",
      "pinyin_hint": "huà · · ·"
    },
    {
      "id": "entry-2",
      "direction": "down",
      "start": { "row": 0, "column": 2 },
      "length": 4,
      "clue": "形容技艺达到纯熟完美的境界",
      "pinyin_hint": "· · · ·"
    }
  ],
  "character_bank": ["龙", "点", "睛", "炉", "火", "纯", "青", "山"],
  "run_id": "run_c42b09b1",
  "saved_state": {
    "grid": ["画", "龙", "", "", "", "", "", ""],
    "elapsed_seconds": 55,
    "hints_used": 0,
    "mistakes": 0
  },
  "limits": {
    "max_hints": 3
  }
}
```

安全要求：

- `cells` 只对固定格返回 `value`。
- `entries` 不得包含成语答案。
- `character_bank` 可以包含干扰字。
- 完整 `solution_json` 不得返回客户端。

### 8.3 保存进度

### `POST /api/idiom/save`

必须登录。

#### 请求

```json
{
  "run_id": "run_c42b09b1",
  "puzzle_id": "idiom-001",
  "grid": ["画", "龙", "点", "", "", "", "", ""],
  "elapsed_seconds": 92,
  "mistakes": 1
}
```

#### 响应

```json
{
  "saved": true,
  "run_id": "run_c42b09b1",
  "updated_at": "2026-07-16T09:40:00Z"
}
```

### 8.4 请求提示

### `POST /api/idiom/hint`

认证可选。

#### 请求

```json
{
  "run_id": "run_c42b09b1",
  "puzzle_id": "idiom-001",
  "grid": ["画", "龙", "", "", "", "", "", ""],
  "entry_id": "entry-1"
}
```

#### 响应

```json
{
  "row": 0,
  "column": 2,
  "value": "点",
  "hints_used": 1,
  "remaining_hints": 2
}
```

优先从 `entry_id` 对应且尚未正确填写的格子中返回提示。

### 8.5 提交答案

### `POST /api/idiom/submit`

认证可选。

#### 请求

```json
{
  "run_id": "run_c42b09b1",
  "puzzle_id": "idiom-001",
  "grid": ["画", "龙", "点", "睛", "火", "纯", "青", "炉"],
  "elapsed_seconds": 186,
  "mistakes": 1,
  "hints_used": 1
}
```

#### 完成响应

```json
{
  "correct": true,
  "status": "completed",
  "result": {
    "score": 784,
    "stars": 2,
    "elapsed_seconds": 186,
    "mistakes": 1,
    "hints_used": 1,
    "earned_stars": 2,
    "total_stars": 10,
    "next_level_id": "idiom-002",
    "is_new_best": true
  }
}
```

#### 错误响应

```json
{
  "correct": false,
  "status": "incorrect",
  "invalid_cells": [3, 6]
}
```

## 9. 记忆翻牌 API

### 9.1 获取牌面

### `GET /api/memory/board`

#### 查询参数

| 参数 | 必填 | 示例 | 说明 |
|---|---:|---|---|
| `mode` | 是 | `daily` | `daily` 或 `practice` |
| `difficulty` | 是 | `easy` | `easy`、`medium`、`hard` |
| `theme` | 否 | `fruit` | 默认 `classic` |
| `fresh` | 否 | `1` | 练习模式传 `1` 时创建全新牌局，不恢复上一局 |

建议棋盘：

| 难度 | 行列 | 配对数 |
|---|---:|---:|
| easy | 4 × 4 | 8 |
| medium | 4 × 5 | 10 |
| hard | 5 × 6 | 15 |

#### 响应

```json
{
  "board_id": "memory-2026-07-16-medium",
  "mode": "daily",
  "puzzle_date": "2026-07-16",
  "difficulty": "medium",
  "theme": "fruit",
  "rows": 4,
  "columns": 5,
  "cards": [
    { "position": 0, "face_key": "apple", "display": "🍎" },
    { "position": 1, "face_key": "banana", "display": "🍌" },
    { "position": 2, "face_key": "apple", "display": "🍎" }
  ],
  "run_id": "run_ef692bda",
  "saved_state": {
    "matched_positions": [0, 2],
    "moves": 3,
    "elapsed_seconds": 22
  }
}
```

说明：

- 每个 `face_key` 必须恰好出现两次。
- 每日牌面按服务端日期固定，所有用户顺序一致。
- `display` 首版可以直接返回 Emoji；后续图片主题返回小程序本地资源 key，不返回任意外链。
- 客户端能够看到牌面数据，因此记忆翻牌成绩不作为强防作弊排行榜依据。

### 9.2 保存进度

### `POST /api/memory/save`

必须登录。

#### 请求

```json
{
  "run_id": "run_ef692bda",
  "board_id": "memory-2026-07-16-medium",
  "matched_positions": [0, 2, 4, 11],
  "moves": 7,
  "elapsed_seconds": 48
}
```

#### 响应

```json
{
  "saved": true,
  "run_id": "run_ef692bda",
  "updated_at": "2026-07-16T09:48:00Z"
}
```

后台至少校验：

- `matched_positions` 不重复且都在棋盘范围内。
- 每组已匹配位置的 `face_key` 相同。
- `moves` 不小于已匹配配对数。
- `elapsed_seconds` 不小于历史保存值。

### 9.3 提交完成结果

### `POST /api/memory/submit`

认证可选。

#### 请求

```json
{
  "run_id": "run_ef692bda",
  "board_id": "memory-2026-07-16-medium",
  "matched_positions": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
  "moves": 18,
  "elapsed_seconds": 96
}
```

#### 响应

```json
{
  "correct": true,
  "status": "completed",
  "result": {
    "score": 812,
    "stars": 3,
    "moves": 18,
    "elapsed_seconds": 96,
    "is_new_best": true
  }
}
```

## 10. 计分和星级建议

计分必须由后端计算，不能接受客户端直接提交 `score` 或 `stars`。

### 10.1 数独

```text
基础分：easy=1000，medium=1500，hard=2000
score = max(100, 基础分 - elapsed_seconds - hints_used*120 - mistakes*20)
```

三星参考：

- 没有使用提示。
- easy 在 10 分钟内，medium 在 15 分钟内，hard 在 25 分钟内。

二星参考：

- 提示不超过 2 次。
- 完成时间不超过三星阈值的 2 倍。

其他完成情况为一星。

### 10.2 成语填字

```text
score = max(100, 1000 - elapsed_seconds - hints_used*120 - mistakes*30)
```

- 0 次提示且错误不超过 1 次：三星。
- 提示不超过 2 次：二星。
- 其他完成情况：一星。

### 10.3 记忆翻牌

```text
pair_count = rows * columns / 2
score = max(100, 1000 - (moves-pair_count)*35 - elapsed_seconds*2)
```

- 步数不超过 `pair_count * 1.5`：三星。
- 步数不超过 `pair_count * 2.5`：二星。
- 其他完成情况：一星。

所有阈值建议放在后端配置文件中，便于上线后调整。

## 11. 题库和内容要求

### 11.1 数独

后台需要提供：

- 每种难度至少 100 道题作为首版库存。
- 每道题必须经过求解器验证唯一解。
- 提供一个离线导入或生成脚本。
- 运行时接口不得现场生成复杂数独，避免响应时间不稳定。

### 11.2 成语

后台需要提供经过审核的成语数据：

```json
{
  "word": "画龙点睛",
  "pinyin": "huà lóng diǎn jīng",
  "definition": "比喻在关键处加上一笔，使内容更加生动。",
  "category": "典故"
}
```

要求：

- 只收录标准四字成语。
- 释义、拼音和用字必须人工或权威来源复核。
- 首版至少准备 60 个可玩的交叉填字关卡。
- 使用离线脚本组题，生成后保存布局，不在请求期间动态搜索布局。

### 11.3 记忆翻牌

首版主题建议：

- `classic`：几何符号。
- `fruit`：水果 Emoji。
- `animal`：动物 Emoji。

后台返回稳定的 `face_key`，展示资源由小程序按照 key 映射。

## 12. 安全、幂等和数据校验

1. 数独和成语的完整答案只保存在后端。
2. 所有完成结果由后端重新计算分数和星级。
3. `run_id` 必须属于当前 Token 用户，不能操作其他用户记录。
4. 对同一个已完成 `run_id` 重复提交，应返回第一次完成结果。
5. 每日完成次数只累计一次。
6. 保存接口不能把 `elapsed_seconds`、`moves` 或已完成格数回退。
7. 提示接口必须由后端累计次数，不能信任客户端提交的 `hints_used`。
8. 未解锁的成语关卡返回 `403`。
9. 日志不能记录 Token、数独完整答案或成语完整解答。
10. 所有 JSON 字段需限制长度和数组大小。

## 13. 性能要求

- 普通题目获取接口目标响应时间低于 500ms。
- 提交校验目标响应时间低于 500ms。
- 数独唯一解校验在题库导入阶段完成，不放在普通请求路径。
- SQLite 继续开启 WAL。
- 查询 `game_runs` 必须使用用户、游戏和更新时间索引。
- 大厅接口应使用少量聚合查询，不能为每个游戏循环发起大量 SQL。

## 14. 后台需要交付给小程序开发的内容

后台完成后，请提供以下内容：

1. 可访问的测试环境 API 地址。
2. 一个测试账号和对应登录方式。
3. 本文档中全部接口的实际请求、响应示例。
4. 最终确认的错误 `code` 列表。
5. 数独题目、成语关卡和记忆主题的测试数据范围。
6. 数据库迁移或自动建表代码。
7. Postman、Apifox 或 OpenAPI 文件，任选一种。
8. `/api/games/overview` 中四个游戏的实际返回结果。
9. 每个游戏至少一个未完成存档和一个已完成结果样例。
10. 部署版本号或 Git 提交号，方便联调时确认版本。

## 15. 联调顺序

建议按以下顺序交付，避免三个游戏同时联调：

1. 数据库表和 `/api/games/overview`。
2. 记忆翻牌三个接口。
3. 数独题目、保存、提示、提交接口。
4. 成语目录、题目、保存、提示、提交接口。
5. 游客流程、登录存档恢复、重复提交测试。
6. 部署测试环境后进行真机联调。

## 16. 后端验收清单

- [ ] 数据库升级不会影响现有用户、猜词存档、闯关和双人房间。
- [ ] 未登录用户可以获取三种游戏题目。
- [ ] 未登录用户调用云保存接口返回 `401`。
- [ ] 登录用户重新打开同一题能恢复未完成状态。
- [ ] 数独题目全部拥有唯一解。
- [ ] 数独接口不返回完整解答。
- [ ] 成语接口不返回完整答案。
- [ ] 成语关卡按顺序解锁。
- [ ] 每日题以服务端日期为准且当天固定。
- [ ] 提示次数由服务端累计。
- [ ] 重复提交不会重复增加星星或完成次数。
- [ ] 大厅接口能正确返回四款游戏的状态和进度。
- [ ] 所有失败响应都有用户可读的 `error` 字段。
- [ ] 现有猜词、闯关、登录和双人接口回归测试通过。
