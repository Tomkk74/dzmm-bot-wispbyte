#!/usr/bin/env bash
# Vultr / VPS 一键安装 DZMM Bot（Ubuntu 22.04/24.04）
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/dzmm-bot}"
REPO="${REPO:-https://github.com/Tomkk74/dzmm-bot-wispbyte.git}"
DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-admin@example.com}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 root 运行：sudo bash install-vultr.sh"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv git curl ca-certificates

if [[ ! -d "$APP_DIR/.git" ]]; then
  mkdir -p "$(dirname "$APP_DIR")"
  git clone -b main "$REPO" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only || true
fi

cd "$APP_DIR"
python3 -m venv .venv
# 标准库即可，venv 只是隔离环境
.venv/bin/python -c "import sys; print(sys.version)"

if [[ ! -f "$APP_DIR/env.txt" ]]; then
  cp env.example.txt env.txt
  echo "已生成 $APP_DIR/env.txt —— 请填 Token/Secret/ADMIN_PASSWORD/PUBLIC_BASE"
fi

# systemd
cat >/etc/systemd/system/dzmm-bot.service <<EOF
[Unit]
Description=DZMM Bot WispByte/Vultr
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=-$APP_DIR/env.txt
Environment=PORT=8787
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/main.py
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable dzmm-bot

echo ""
echo "==== 下一步 ===="
echo "1) 编辑：$APP_DIR/env.txt"
echo "   DZMM_BOT_TOKEN=..."
echo "   DZMM_BOT_SECRET=..."
echo "   ADMIN_PASSWORD=..."
echo "   PUBLIC_BASE=https://你的域名   # 先可填 http://服务器IP:8787 测通"
echo "   PORT=8787"
echo "   DZMM_API_BASE=https://www.dzmm.ai"
echo "2) 放行防火墙 / Vultr Firewall：TCP 8787（以及后面 HTTPS 的 80/443）"
echo "3) systemctl restart dzmm-bot && systemctl status dzmm-bot"
echo "4) curl http://127.0.0.1:8787/health"
echo ""
if [[ -n "$DOMAIN" ]]; then
  apt-get install -y caddy
  cat >/etc/caddy/Caddyfile <<EOF2
$DOMAIN {
  reverse_proxy 127.0.0.1:8787
}
EOF2
  systemctl enable --now caddy
  systemctl reload caddy || systemctl restart caddy
  echo "已配置 Caddy：$DOMAIN → 127.0.0.1:8787"
  echo "请把 PUBLIC_BASE 改成 https://$DOMAIN 后：systemctl restart dzmm-bot"
  echo "Studio Webhook：https://$DOMAIN/webhook"
else
  echo "有域名后执行："
  echo "  DOMAIN=bot.example.com EMAIL=你@邮箱.com bash $APP_DIR/install-vultr.sh"
  echo "或手动装 Caddy 反代到 127.0.0.1:8787"
fi
