#!/usr/bin/env bash
set -euo pipefail

POWERCLAW_HOME="${POWERCLAW_HOME:-/opt/powerclaw}"
POWERCLAW_USER="${POWERCLAW_USER:-powerclaw}"
POWERCLAW_BACKUP_DIR="${POWERCLAW_BACKUP_DIR:-/var/backups/powerclaw}"
POWERCLAW_DOMAIN="${POWERCLAW_DOMAIN:-}"
POWERCLAW_TLS_EMAIL="${POWERCLAW_TLS_EMAIL:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root, for example: sudo POWERCLAW_DOMAIN=agent.example.com POWERCLAW_TLS_EMAIL=you@example.com bash scripts/harden-ec2.sh" >&2
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y nginx certbot python3-certbot-nginx sqlite3
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y nginx certbot python3-certbot-nginx sqlite
elif command -v yum >/dev/null 2>&1; then
  yum install -y nginx certbot python3-certbot-nginx sqlite
else
  echo "Unsupported package manager. Install nginx, certbot, and sqlite manually." >&2
  exit 1
fi

install -d -m 0750 -o "$POWERCLAW_USER" -g "$POWERCLAW_USER" "$POWERCLAW_BACKUP_DIR"
install -m 0755 "$POWERCLAW_HOME/scripts/backup-state.sh" /usr/local/bin/powerclaw-backup-state
cp "$POWERCLAW_HOME/deploy/ec2/powerclaw-backup.service" /etc/systemd/system/powerclaw-backup.service
cp "$POWERCLAW_HOME/deploy/ec2/powerclaw-backup.timer" /etc/systemd/system/powerclaw-backup.timer

nginx_available="/etc/nginx/sites-available"
nginx_enabled="/etc/nginx/sites-enabled"
if [[ -d "$nginx_available" && -d "$nginx_enabled" ]]; then
  cp "$POWERCLAW_HOME/deploy/ec2/powerclaw.nginx.conf" "$nginx_available/powerclaw"
  if [[ -n "$POWERCLAW_DOMAIN" ]]; then
    sed -i "s/server_name _;/server_name $POWERCLAW_DOMAIN;/" "$nginx_available/powerclaw"
  fi
  ln -sf "$nginx_available/powerclaw" "$nginx_enabled/powerclaw"
  rm -f "$nginx_enabled/default"
else
  cp "$POWERCLAW_HOME/deploy/ec2/powerclaw.nginx.conf" /etc/nginx/conf.d/powerclaw.conf
  if [[ -n "$POWERCLAW_DOMAIN" ]]; then
    sed -i "s/server_name _;/server_name $POWERCLAW_DOMAIN;/" /etc/nginx/conf.d/powerclaw.conf
  fi
fi

nginx -t
systemctl enable --now nginx

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow OpenSSH
  ufw allow "Nginx Full"
  ufw deny 8765/tcp || true
fi

if [[ -n "$POWERCLAW_DOMAIN" ]]; then
  if [[ -z "$POWERCLAW_TLS_EMAIL" ]]; then
    echo "POWERCLAW_TLS_EMAIL is required when POWERCLAW_DOMAIN is set." >&2
    exit 1
  fi
  certbot --nginx \
    --non-interactive \
    --agree-tos \
    --redirect \
    -m "$POWERCLAW_TLS_EMAIL" \
    -d "$POWERCLAW_DOMAIN"
fi

systemctl daemon-reload
systemctl enable --now powerclaw-backup.timer
systemctl restart nginx

echo "PowerClaw hardening installed."
echo "Reverse proxy: nginx"
echo "Backups: systemctl list-timers powerclaw-backup.timer"
