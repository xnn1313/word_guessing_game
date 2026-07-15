# 猜词游戏微信小程序（开发版）

这是现有猜词游戏的原生微信小程序客户端，复用同一套 Flask API、账号、SQLite 存档、
260 个分类关卡和双人房间。当前开发版使用用户名/密码和 Bearer Token，不需要微信 AppID
即可先在开发者工具中联调。

## 已实现

- 首页、账号登录/注册和个人进度
- 经典猜词、相似度/时间排序、查看答案和重置
- 13 个分类、260 关、解锁、星级和下一关
- 双人创建/加入房间、实时比分、倒计时、猜测记录和双方再战
- Token 哈希存储，网页 Cookie 登录保持兼容

## 在微信开发者工具中打开

1. 在电脑上安装微信开发者工具。
2. 导入项目目录 `word_guessing_game/miniprogram`。
3. 没有 AppID 时保留 `project.config.json` 中的 `touristappid`；有测试 AppID 时在工具里替换。
4. 打开“详情 → 本地设置”，勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。
5. 修改 `config/index.ts` 中的 `API_BASE`：

   ```ts
   export const API_BASE = "http://你的服务器IP:5000/api";
   ```

   `127.0.0.1` 指的是运行微信开发者工具的电脑，不是远程服务器。若开发者工具和后端不在
   同一台机器，必须填写电脑可以访问到的服务器地址。

6. 确保后端服务已经重启并包含 `/api/mobile/auth/login` 接口，然后点击“编译”。

## 本地检查

```bash
cd miniprogram
npm install
npm run check
```

## 开发阶段的安全提醒

用户名和密码不应通过公网 HTTP 传输。如果从外网联调，请至少通过 VPN/SSH 隧道访问，
或提前给测试域名配置 HTTPS。正式发布时还需换成合法 HTTPS 域名，并接入 `wx.login`；
AppSecret 只能放在服务器环境变量中。

## 当前限制

- 双人状态沿用现有每秒轮询，后续可升级为 WebSocket + Redis。
- `touristappid` 适合界面开发；好友分享和两台真机联调需要自己的测试 AppID。
- Linux 服务器不能运行官方微信开发者工具，最终视觉和真机交互需要在 Windows/macOS 工具中确认。
