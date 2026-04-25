from __future__ import annotations

"""SQLite-backed memory storage for PowerClaw."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading

from powerclaw.memory.manager import MemoryBackend, MemoryItem, MemoryQuery

SCHEMA_VERSION = 1


class SQLiteMemoryBackend(MemoryBackend):
    """Durable memory backend using a compact SQLite schema."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def append(self, item: MemoryItem) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_items (kind, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    item.kind,
                    item.content,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.created_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        text = query.text.strip()
        limit = max(1, query.limit)
        clauses = []
        params: list[object] = []
        if query.kinds:
            placeholders = ",".join("?" for _ in query.kinds)
            clauses.append(f"kind IN ({placeholders})")
            params.extend(query.kinds)
        if text:
            clauses.append("LOWER(content) LIKE ?")
            params.append(f"%{text.lower()}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT kind, content, metadata_json, created_at
            FROM memory_items
            {where}
            ORDER BY id ASC
            LIMIT ?
        """
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_item(row) for row in rows]

    def list_items(self) -> list[MemoryItem]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT kind, content, metadata_json, created_at
                FROM memory_items
                ORDER BY id ASC
                """
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memory_items_kind ON memory_items(kind);
                CREATE INDEX IF NOT EXISTS idx_memory_items_created_at ON memory_items(created_at);
                """
            )
            row = self._conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
            if row is None:
                self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            self._conn.commit()


def _row_to_item(row: sqlite3.Row) -> MemoryItem:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return MemoryItem(
        kind=row["kind"],
        content=row["content"],
        metadata=metadata,
        created_at=created_at,
    )
