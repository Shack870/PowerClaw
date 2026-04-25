from __future__ import annotations

"""Durable runtime state storage for PowerClaw sessions and turns."""

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Protocol

from powerclaw.runtime.state import MessageRecord, SessionState, ToolCallRecord, TurnRecord


class StateStore(Protocol):
    """Storage contract for durable runtime state."""

    def save_session(self, session: SessionState) -> None:
        ...

    def load_session(self, session_id: str) -> SessionState | None:
        ...

    def list_sessions(self, *, limit: int = 50) -> list[SessionState]:
        ...


class NullStateStore:
    """No-op state store used when durable sessions are disabled."""

    def save_session(self, session: SessionState) -> None:
        return None

    def load_session(self, session_id: str) -> SessionState | None:
        return None

    def list_sessions(self, *, limit: int = 50) -> list[SessionState]:
        return []


class SQLiteStateStore:
    """SQLite-backed session and turn store."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def save_session(self, session: SessionState) -> None:
        """Persist a complete session snapshot."""
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    session_id, task_id, platform, active_skill_ids_json,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.task_id,
                    session.platform,
                    _json_dump(session.active_skill_ids),
                    _json_dump(session.metadata),
                    _dt(session.created_at),
                    _dt(session.updated_at),
                ),
            )
            self._conn.execute("DELETE FROM session_messages WHERE session_id = ?", (session.session_id,))
            for index, message in enumerate(session.history):
                self._conn.execute(
                    """
                    INSERT INTO session_messages (
                        session_id, position, role, content, name, metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    _message_row(session.session_id, index, message),
                )

            self._conn.execute("DELETE FROM turns WHERE session_id = ?", (session.session_id,))
            for index, turn in enumerate(session.turns):
                self._conn.execute(
                    """
                    INSERT INTO turns (
                        turn_id, session_id, position, user_input, model, metadata_json,
                        started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        turn.id,
                        session.session_id,
                        index,
                        turn.user_input,
                        turn.model,
                        _json_dump(turn.metadata),
                        _dt(turn.started_at),
                        _dt(turn.completed_at) if turn.completed_at else None,
                    ),
                )
                self._conn.execute("DELETE FROM turn_messages WHERE turn_id = ?", (turn.id,))
                for message_index, message in enumerate(turn.messages):
                    self._conn.execute(
                        """
                        INSERT INTO turn_messages (
                            turn_id, position, role, content, name, metadata_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        _turn_message_row(turn.id, message_index, message),
                    )
                self._conn.execute("DELETE FROM tool_calls WHERE turn_id = ?", (turn.id,))
                for tool_index, tool_call in enumerate(turn.tool_calls):
                    self._conn.execute(
                        """
                        INSERT INTO tool_calls (
                            turn_id, position, call_id, tool_name, arguments_json,
                            status, result_json, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            turn.id,
                            tool_index,
                            tool_call.call_id,
                            tool_call.tool_name,
                            _json_dump(tool_call.arguments),
                            tool_call.status,
                            _json_dump({"value": tool_call.result}),
                            _json_dump(tool_call.metadata),
                        ),
                    )
            self._conn.commit()

    def load_session(self, session_id: str) -> SessionState | None:
        """Load a session snapshot by id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            message_rows = self._conn.execute(
                """
                SELECT * FROM session_messages
                WHERE session_id = ?
                ORDER BY position ASC
                """,
                (session_id,),
            ).fetchall()
            turn_rows = self._conn.execute(
                """
                SELECT * FROM turns
                WHERE session_id = ?
                ORDER BY position ASC
                """,
                (session_id,),
            ).fetchall()
            turn_messages = {
                turn_row["turn_id"]: self._conn.execute(
                    """
                    SELECT * FROM turn_messages
                    WHERE turn_id = ?
                    ORDER BY position ASC
                    """,
                    (turn_row["turn_id"],),
                ).fetchall()
                for turn_row in turn_rows
            }
            tool_calls = {
                turn_row["turn_id"]: self._conn.execute(
                    """
                    SELECT * FROM tool_calls
                    WHERE turn_id = ?
                    ORDER BY position ASC
                    """,
                    (turn_row["turn_id"],),
                ).fetchall()
                for turn_row in turn_rows
            }

        session = SessionState(
            session_id=row["session_id"],
            task_id=row["task_id"],
            platform=row["platform"],
            active_skill_ids=list(_json_load(row["active_skill_ids_json"], [])),
            metadata=dict(_json_load(row["metadata_json"], {})),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )
        session.history = [_row_to_message(message_row) for message_row in message_rows]
        session.turns = [
            _row_to_turn(
                turn_row,
                message_rows=turn_messages.get(turn_row["turn_id"], []),
                tool_rows=tool_calls.get(turn_row["turn_id"], []),
            )
            for turn_row in turn_rows
        ]
        return session

    def list_sessions(self, *, limit: int = 50) -> list[SessionState]:
        """List recent sessions without loading full history."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM sessions
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        sessions: list[SessionState] = []
        for row in rows:
            sessions.append(
                SessionState(
                    session_id=row["session_id"],
                    task_id=row["task_id"],
                    platform=row["platform"],
                    active_skill_ids=list(_json_load(row["active_skill_ids_json"], [])),
                    metadata=dict(_json_load(row["metadata_json"], {})),
                    created_at=_parse_datetime(row["created_at"]),
                    updated_at=_parse_datetime(row["updated_at"]),
                )
            )
        return sessions

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    platform TEXT NOT NULL,
                    active_skill_ids_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS session_messages (
                    session_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, position),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    user_input TEXT NOT NULL,
                    model TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS turn_messages (
                    turn_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    name TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (turn_id, position),
                    FOREIGN KEY (turn_id) REFERENCES turns(turn_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tool_calls (
                    turn_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    call_id TEXT,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (turn_id, position),
                    FOREIGN KEY (turn_id) REFERENCES turns(turn_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
                CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, position);
                """
            )
            self._conn.commit()


def build_state_store_from_settings(settings: Any) -> StateStore:
    """Build a runtime state store from settings."""
    backend = getattr(settings.memory, "session_backend", "memory")
    if backend == "sqlite":
        return SQLiteStateStore(settings.memory.state_db_path)
    return NullStateStore()


def _message_row(session_id: str, index: int, message: MessageRecord) -> tuple[object, ...]:
    return (
        session_id,
        index,
        message.role,
        message.content,
        message.name,
        _json_dump(message.metadata),
        _dt(message.created_at),
    )


def _turn_message_row(turn_id: str, index: int, message: MessageRecord) -> tuple[object, ...]:
    return (
        turn_id,
        index,
        message.role,
        message.content,
        message.name,
        _json_dump(message.metadata),
        _dt(message.created_at),
    )


def _row_to_message(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        role=row["role"],
        content=row["content"],
        name=row["name"],
        metadata=dict(_json_load(row["metadata_json"], {})),
        created_at=_parse_datetime(row["created_at"]),
    )


def _row_to_turn(
    row: sqlite3.Row,
    *,
    message_rows: list[sqlite3.Row],
    tool_rows: list[sqlite3.Row],
) -> TurnRecord:
    turn = TurnRecord(
        user_input=row["user_input"],
        model=row["model"],
        metadata=dict(_json_load(row["metadata_json"], {})),
        started_at=_parse_datetime(row["started_at"]),
        completed_at=_parse_datetime(row["completed_at"]) if row["completed_at"] else None,
    )
    turn = replace(turn, id=row["turn_id"])
    turn.messages = [_row_to_message(message_row) for message_row in message_rows]
    turn.tool_calls = [_row_to_tool_call(tool_row) for tool_row in tool_rows]
    return turn


def _row_to_tool_call(row: sqlite3.Row) -> ToolCallRecord:
    result = _json_load(row["result_json"], {})
    if isinstance(result, dict) and "value" in result:
        result_value = result["value"]
    else:
        result_value = result
    return ToolCallRecord(
        call_id=row["call_id"],
        tool_name=row["tool_name"],
        arguments=dict(_json_load(row["arguments_json"], {})),
        status=row["status"],
        result=result_value,
        metadata=dict(_json_load(row["metadata_json"], {})),
    )


def _json_dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _json_load(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
