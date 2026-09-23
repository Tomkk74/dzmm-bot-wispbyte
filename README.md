# DZMM Bot · 独立版（Python）

与现网 Cloudflare「小哈」分开部署。本机出网发消息，一般无 CF 418。

## Vultr / VPS（推荐）

系统选 **Ubuntu 22.04 或 24.04**，机房优先 **Singapore / Tokyo**。

```bash
# SSH 登录后（root）
curl -fsSL -o /tmp/install-vultr.sh https://raw.githubusercontent.com/Tomkk74/dzmm-bot-wispbyte/main/install-vultr.sh
bash /tmp/install-vultr.sh
```

有域名时（自动 HTTPS，推荐）：

```bash
DOMAIN=你的域名.com bash /tmp/install-vultr.sh
```

然后编辑 `/opt/dzmm-bot/env.txt`：

```text
DZMM_BOT_TOKEN=你的Token
DZMM_BOT_SECRET=你的WebhookSecret
ADMIN_PASSWORD=自设后台密码
PUBLIC_BASE=https://你的域名
PORT=8787
DZMM_API_BASE=https://www.dzmm.ai
```

```bash
systemctl restart dzmm-bot
curl -sS https://你的域名/health
```

Studio Webhook：`https://你的域名/webhook`

DNS：A 记录指到 Vultr 公网 IP。防火墙放行 **80 / 443**。

## WispByte（旧面板）

Git：`https://github.com/Tomkk74/dzmm-bot-wispbyte.git`  
Environment 填 Token / Secret / PUBLIC_BASE / PORT。

## 能力

帮助 / 你好 / ping / 骰子 / 抽签 / `/画` / 后台 `/admin/`

不要把 `env.txt` 提交进 Git。
