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

继续使用原有小程序登录接口：

```http
POST /api/mobile/auth/register
POST /api/mobile/auth/login
Authorization: Bearer <token>
```

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
- `HINT_LIMIT_REACHED`
- `NO_HINT_AVAILABLE`
- `LEVEL_LOCKED`
- `INTERNAL_ERROR`

## 自动化验证

```bash
cd backend
../.venv/bin/python -m unittest -v test_puzzle_api.py test_external_puzzle_import.py
```

测试覆盖游客读取、登录云存档、每日题固定、提示恢复、错误提交、成语解锁、翻牌配对校验、后端计分、重复提交幂等，以及外部题库的事务回滚、去重和不可变性。

游客成语目录默认只标记每个分类第一关为已解锁；游客完成状态由小程序本地保存和覆盖，后台允许游客读取任意有效普通关卡。登录用户仍由后台严格校验关卡顺序。

数独和成语存档允许擦除或改写普通输入格，只禁止修改数独给定格和成语固定格。`elapsed_seconds`、`mistakes` 以及翻牌已匹配位置仍不能回退。
