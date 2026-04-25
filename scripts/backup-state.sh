#!/usr/bin/env bash
set -euo pipefail

POWERCLAW_STATE_DB_PATH="${POWERCLAW_STATE_DB_PATH:-/var/lib/powerclaw/state.db}"
POWERCLAW_BACKUP_DIR="${POWERCLAW_BACKUP_DIR:-/var/backups/powerclaw}"
POWERCLAW_BACKUP_RETENTION_DAYS="${POWERCLAW_BACKUP_RETENTION_DAYS:-14}"

if [[ ! -f "$POWERCLAW_STATE_DB_PATH" ]]; then
  echo "State DB does not exist yet: $POWERCLAW_STATE_DB_PATH"
  exit 0
fi

mkdir -p "$POWERCLAW_BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$POWERCLAW_BACKUP_DIR/state-$timestamp.db"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$POWERCLAW_STATE_DB_PATH" ".backup '$backup_path'"
else
  cp "$POWERCLAW_STATE_DB_PATH" "$backup_path"
fi

chmod 600 "$backup_path"
find "$POWERCLAW_BACKUP_DIR" -type f -name 'state-*.db' -mtime +"$POWERCLAW_BACKUP_RETENTION_DAYS" -delete
echo "$backup_path"
