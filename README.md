# 猜词游戏

基于 BGE 模型的 Web 猜词游戏。系统从随机词库中选择目标词，用户输入猜测词，系统使用 BGE 模型返回语义相似度百分比。

## 安装 & 运行

```bash
cd backend
pip install -r requirements.txt
python app.py
```

打开浏览器访问 `http://localhost:5000`

## 登录与存档

页面右上角可注册或登录账号。登录后，每次猜词、查看答案和重置游戏都会自动保存到
`backend/word_guessing_game.db`，再次进入并登录同一账号即可恢复当前轮次和历史记录。

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WORD_GAME_SECRET_KEY` | 开发用固定值 | 登录 Cookie 签名密钥；`WORD_GAME_ENV=production` 时缺失会拒绝启动 |
| `WORD_GAME_ENV` | `development` | 设为 `production` 启用生产校验（密钥必填、关闭 debug） |
| `WORD_GAME_CORS_ORIGINS` | 空 | 逗号分隔的跨域白名单；小程序与同源网页无需配置 |
| `WORD_GAME_DEBUG` | `0` | 设为 `1` 才开启 Flask debug 与 DEBUG 日志 |
| `WORD_GAME_DB_PATH` | `backend/word_guessing_game.db` | SQLite 路径，测试时指向临时库 |
| `WORD_GAME_SESSION_TTL_SECONDS` | `43200` | 内存对局会话的空闲过期时间 |
| `WORD_GAME_SESSION_MAX_ENTRIES` | `2000` | 内存会话上限，超出后淘汰最久未活跃的会话 |

生产运行使用 `word-guessing-game.service`（gunicorn），不要用 `python app.py`。

## 测试

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
```

测试覆盖经典/闯关/对战之外的益智游戏接口、插件注册表契约、SQLite 迁移、会话过期与限流、统一错误协议。新增游戏后 `test_games_registry.py` 会自动带上它。

## 分类闯关

登录后可切换到“分类闯关”模式。当前提供 13 个分类，每类 20 关，共 260 关。
每 4 关提升一档难度，从入门逐步到大师。关卡按顺序解锁，5 次内猜中获得三星、
10 次内获得二星，其余获得一星；历史最佳成绩
保存在 SQLite 数据库中。

## 双人在线竞速

登录后可创建六位房间码并邀请另一名玩家加入。房主在两人到齐后开始 90 秒比赛，
双方猜同一个隐藏词；页面每秒同步次数与最高相似度，先猜中者获胜。比赛结束后，
双方都点击“再来一局”便会自动更换目标词并开始下一轮。基础版房间状态保存在运行
内存中，服务重启会结束尚未完成的房间。每位玩家已经遇到过的双人答案会永久记录
在 SQLite 中；出题会避开双方的历史答案，题库全部用完后才从最久未出现的答案开始复用。

## 微信小程序开发版

`miniprogram/` 提供原生 TypeScript 微信小程序客户端，已覆盖账号、经典猜词、分类闯关、
双人竞速，以及数独、成语填字、记忆翻牌、成语连线、诗词大会、推箱子和箭头迷宫。
三款新增游戏均提供每日挑战、自由练习、游客本地续玩和登录云存档。开发阶段可使用
`touristappid`，并在微信开发者工具中关闭合法域名校验；具体
导入和接口地址配置参见 [`miniprogram/README.md`](miniprogram/README.md)。

诗词大会现有 1468 首去重作品，三个难度题池分别为 427 / 861 / 1468 首，每局为
12 / 20 / 30 题。每日题按固定轮换表取题，相邻日期不重复，单首作品至少间隔
35 / 43 / 48 天才会再次进入对应难度的每日题组；自由练习每次可随机换一组。

## 项目结构

```
├── backend/
│   ├── app.py          # Flask API
│   ├── similarity.py   # BGE 语义相似度计算
│   ├── word_bank.py    # 词库管理
│   ├── game_manager.py # 游戏状态管理
│   ├── config.py       # 配置文件
│   ├── words.json      # 词库
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```
