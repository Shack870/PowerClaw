#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(
  cd "$ROOT_DIR"
  python3 - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT_DIR/dist}"
ARTIFACT_NAME="${ARTIFACT_NAME:-powerclaw-ec2-$VERSION.tar.gz}"
ARTIFACT_PATH="$ARTIFACT_DIR/$ARTIFACT_NAME"

mkdir -p "$ARTIFACT_DIR"
cd "$ROOT_DIR"

tar \
  --exclude __pycache__ \
  --exclude "*.pyc" \
  --exclude .pytest_cache \
  --exclude .venv \
  --exclude "*.egg-info" \
  -czf "$ARTIFACT_PATH" \
  .gitignore \
  POWERCLAW_ARCHITECTURE.md \
  POWERCLAW_ROADMAP.md \
  pyproject.toml \
  uv.lock \
  powerclaw \
  deploy/ec2 \
  docs/deploy \
  scripts/backup-state.sh \
  scripts/harden-ec2.sh \
  scripts/install-ec2.sh \
  scripts/package-ec2.sh

echo "$ARTIFACT_PATH"
