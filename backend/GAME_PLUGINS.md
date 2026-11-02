# 新增一个益智游戏

益智游戏的 HTTP 接口、鉴权、请求校验、游客提示次数和状态码策略现在都在
`routes/games.py` 里统一处理。新增游戏只需要一个业务模块和一个适配模块。

## 1. 业务模块

实现游戏本身的规则，例如 `my_game.py`：

```python
def get_my_game(user, mode, difficulty, fresh=False):
    ...  # 返回包含 puzzle_id/run_id/棋盘的字典

def save_my_game(user, data): ...
def hint_my_game(user, data, guest_hints): ...
def submit_my_game(user, data, guest_hints): ...
```

游客可玩的游戏要允许 `user is None`；需要登录的操作在模块里抛
`puzzle_games.PuzzleError("登录后才能使用云存档", "AUTH_REQUIRED", 401)`。

## 2. 适配模块

在 `games/my_game.py` 注册即可，路由器会自动获得
`/api/games/my_game/{start,catalog,save,hint,submit}`：

```python
import puzzle_games
from . import register
from .base import GameSpec


def _start(user, params):
    return puzzle_games.get_my_game(
        user, params.get("mode"), params.get("difficulty")
    )


register(
    GameSpec(
        key="my_game",
        title="我的游戏",
        daily=True,
        levels=30,
        order=80,
        start=_start,
        save=...,
        submit=...,
        overview=lambda ctx: ("今日未完成" if not ctx.daily_completed else "今日已完成", 0),
    )
)
```

最后在 `games/__init__.py` 的 import 列表里加上 `my_game`。游戏总览的条目、
可用游戏数、每日完成数会自动更新，不需要改 `games/overview.py` 或
`puzzle_games.games_overview`。

## 3. 约定

- `status="always_200"` 用于答错也属于正常反馈的游戏（如诗词选择题）；默认
  `422_if_incorrect` 在 `result["correct"]` 为假时返回 422。
- `overview(ctx)` 返回 `(progress_text, progress_percent)`；`ctx.stats` 是该游戏的
  `storage.get_game_run_stats` 行，`ctx.daily_completed` 已按当天算好。
- 旧的逐游戏路径（如 `/api/sudoku/puzzle`）由 `routes/games.py:LEGACY_ROUTES`
  维护；新游戏直接使用通用路径即可，不必再写入口别名。
- `test_games_registry.py` 会遍历注册表验证 start/旧路径/总览，所以注册后测试会
  自动覆盖到新游戏。
