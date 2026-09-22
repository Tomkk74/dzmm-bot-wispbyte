# DZMM Bot · WispByte 独立版（Python）

与现网 Cloudflare「小哈」分开部署。本机出网发消息，一般无 CF 418。

## WispByte 拉取

1. Free → Python 3.11  
2. **Git 仓库**填本仓库 HTTPS 地址（不要拉别的仓）  
3. 启动命令保持跑 `main.py`  
4. 在面板 Environment，或容器里自建 `env.txt`：

```text
DZMM_BOT_TOKEN=你的Token
DZMM_BOT_SECRET=你的WebhookSecret
MOENODE_API_KEY=
PUBLIC_BASE=https://你的公网地址
PORT=面板Address冒号后端口
ADMIN_PASSWORD=自设后台密码
```

也可复制 `env.example.txt` 改名为 `env.txt` 再填。

5. Start 后打开 `PUBLIC_BASE/health` 应看到 `ok: true`  
6. Studio → Bot Webhook 改成：`PUBLIC_BASE/webhook`（Secret 与 env 一致）

## 能力

- `帮助` / `你好` / `ping` / `骰子` / `抽签`
- `/画 描述`（MoeNode → 本地图 → `/img` → sendPhoto）
- 后台：`/admin/`（总管理 + 群管理码）

不含现网迷宫 RPG 全量（以本仓代码为准）。

## 注意

- **不要**把 `env.txt` 提交进 Git  
- 测独立版最好另建一只 Bot，避免抢现网 Webhook  
- 测完若要回 CF 小哈，把 Studio Webhook 改回 `https://dzmm-template-bot.pages.dev/webhook`
