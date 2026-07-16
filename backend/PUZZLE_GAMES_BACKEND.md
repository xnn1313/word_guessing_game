# 益智游戏平台后台联调说明

实现版本：`puzzle-api-v1`

## 启动与初始化

后台启动时会幂等创建新表并补齐题库，不修改 `users.game_state`。也可以手动运行：

```bash
cd backend
../.venv/bin/python scripts/seed_puzzles.py --verify
```

题库范围：

- 数独：`easy`、`medium`、`hard` 各 100 道，共 300 道；由唯一解基础题做保持唯一解的行列和数字置换。
- 成语：3 个分类、每类 20 关，共 60 个双词交叉关卡。
- 记忆翻牌：`classic`、`fruit`、`animal` 三个主题；8、10、15 对三种难度。

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
../.venv/bin/python -m unittest -v test_puzzle_api.py
```

测试覆盖游客读取、登录云存档、每日题固定、提示恢复、错误提交、成语解锁、翻牌配对校验、后端计分和重复提交幂等。
