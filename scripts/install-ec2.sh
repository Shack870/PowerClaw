#!/usr/bin/env bash
set -euo pipefail

POWERCLAW_REPO_URL="${POWERCLAW_REPO_URL:-}"
POWERCLAW_REF="${POWERCLAW_REF:-main}"
POWERCLAW_HOME="${POWERCLAW_HOME:-/opt/powerclaw}"
POWERCLAW_USER="${POWERCLAW_USER:-powerclaw}"
POWERCLAW_DATA_DIR="${POWERCLAW_DATA_DIR:-/var/lib/powerclaw}"
POWERCLAW_ETC_DIR="${POWERCLAW_ETC_DIR:-/etc/powerclaw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root, for example: sudo POWERCLAW_REPO_URL=... bash scripts/install-ec2.sh" >&2
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y git curl ca-certificates python3
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y git curl ca-certificates python3
elif command -v yum >/dev/null 2>&1; then
  yum install -y git curl ca-certificates python3
else
  echo "Unsupported package manager. Install git, curl, ca-certificates, and python3 manually." >&2
  exit 1
fi

if ! id "$POWERCLAW_USER" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "$POWERCLAW_USER"
fi

mkdir -p \
  "$POWERCLAW_HOME" \
  "$POWERCLAW_DATA_DIR/workspace" \
  "$POWERCLAW_DATA_DIR/cache" \
  "$POWERCLAW_DATA_DIR/uv-cache" \
  "$POWERCLAW_ETC_DIR"
chown -R "$POWERCLAW_USER:$POWERCLAW_USER" "$POWERCLAW_HOME" "$POWERCLAW_DATA_DIR"

if [[ -n "$POWERCLAW_REPO_URL" ]]; then
  if [[ -d "$POWERCLAW_HOME/.git" ]]; then
    git -C "$POWERCLAW_HOME" fetch --all --prune
    git -C "$POWERCLAW_HOME" checkout "$POWERCLAW_REF"
    git -C "$POWERCLAW_HOME" pull --ff-only || true
  else
    rm -rf "$POWERCLAW_HOME"
    git clone --branch "$POWERCLAW_REF" "$POWERCLAW_REPO_URL" "$POWERCLAW_HOME"
  fi
elif [[ -f "$SOURCE_DIR/pyproject.toml" && -d "$SOURCE_DIR/powerclaw" ]]; then
  if [[ "$SOURCE_DIR" != "$POWERCLAW_HOME" ]]; then
    rm -rf "$POWERCLAW_HOME"
    mkdir -p "$POWERCLAW_HOME"
    tar -C "$SOURCE_DIR" \
      --exclude .git \
      --exclude .venv \
      --exclude .pytest_cache \
      --exclude __pycache__ \
      --exclude dist \
      -cf - . | tar -C "$POWERCLAW_HOME" -xf -
  fi
else
  echo "Set POWERCLAW_REPO_URL, or run this script from an extracted PowerClaw package." >&2
  exit 1
fi
chown -R "$POWERCLAW_USER:$POWERCLAW_USER" "$POWERCLAW_HOME"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
fi

sudo -u "$POWERCLAW_USER" /usr/local/bin/uv --directory "$POWERCLAW_HOME" sync

if [[ ! -f "$POWERCLAW_ETC_DIR/powerclaw.env" ]]; then
  cp "$POWERCLAW_HOME/deploy/ec2/powerclaw.env.example" "$POWERCLAW_ETC_DIR/powerclaw.env"
  chmod 600 "$POWERCLAW_ETC_DIR/powerclaw.env"
  echo "Created $POWERCLAW_ETC_DIR/powerclaw.env. Edit secrets before starting the service."
fi

cp "$POWERCLAW_HOME/deploy/ec2/powerclaw.service" /etc/systemd/system/powerclaw.service
if [[ -f "$POWERCLAW_HOME/scripts/backup-state.sh" ]]; then
  install -m 0755 "$POWERCLAW_HOME/scripts/backup-state.sh" /usr/local/bin/powerclaw-backup-state
fi
systemctl daemon-reload
systemctl enable powerclaw

echo "PowerClaw installed."
echo "Next:"
echo "  1. Edit $POWERCLAW_ETC_DIR/powerclaw.env"
echo "  2. sudo systemctl start powerclaw"
echo "  3. curl -H 'Authorization: Bearer <token>' http://127.0.0.1:8765/health"
echo "  4. Optional hardening: sudo POWERCLAW_DOMAIN=agent.example.com POWERCLAW_TLS_EMAIL=you@example.com bash $POWERCLAW_HOME/scripts/harden-ec2.sh"
