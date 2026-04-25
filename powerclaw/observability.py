from __future__ import annotations

"""Runtime event recording and summary metrics for PowerClaw."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Any, Protocol


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for event records."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RuntimeEvent:
    """A single observable runtime event."""

    id: str
    event_type: str
    level: str = "info"
    session_id: str | None = None
    turn_id: str | None = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable event payload."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "level": self.level,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "message": self.message,
            "payload": dict(self.payload),
            "created_at": self.created_at.isoformat(),
        }


class ObservabilitySink(Protocol):
    """Storage contract for runtime events."""

    def record(self, event: RuntimeEvent) -> RuntimeEvent:
        ...

    def list_events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[RuntimeEvent]:
        ...


class InMemoryObservabilitySink:
    """In-process event store."""

    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []
        self._lock = threading.Lock()

    def record(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._lock:
            self._events.append(event)
        return event

    def list_events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[RuntimeEvent]:
        with self._lock:
            events = list(self._events)
        filtered = [
            event
            for event in events
            if (session_id is None or event.session_id == session_id)
            and (turn_id is None or event.turn_id == turn_id)
        ]
        return filtered[-max(1, limit) :]


class SQLiteObservabilitySink:
    """SQLite-backed event store shared with PowerClaw state."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def record(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO runtime_events (
                    id, event_type, level, session_id, turn_id, message,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.event_type,
                    event.level,
                    event.session_id,
                    event.turn_id,
                    event.message,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.created_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()
        return event

    def list_events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[RuntimeEvent]:
        clauses = []
        params: list[object] = []
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if turn_id is not None:
            clauses.append("turn_id = ?")
            params.append(turn_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, limit))
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM runtime_events
                {where}
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return list(reversed([_row_to_event(row) for row in rows]))

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    session_id TEXT,
                    turn_id TEXT,
                    message TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runtime_events_created_at
                    ON runtime_events(created_at);
                CREATE INDEX IF NOT EXISTS idx_runtime_events_session
                    ON runtime_events(session_id, turn_id);
                CREATE INDEX IF NOT EXISTS idx_runtime_events_type
                    ON runtime_events(event_type);
                """
            )
            self._conn.commit()


class ObservabilityManager:
    """Records runtime events and derives lightweight dashboard metrics."""

    def __init__(self, sink: ObservabilitySink | None = None) -> None:
        self.sink = sink or InMemoryObservabilitySink()

    def record_event(
        self,
        event_type: str,
        *,
        level: str = "info",
        session_id: str | None = None,
        turn_id: str | None = None,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        """Persist one runtime event."""
        return self.sink.record(
            RuntimeEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                level=level,
                session_id=session_id,
                turn_id=turn_id,
                message=message,
                payload=payload or {},
            )
        )

    def list_events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[RuntimeEvent]:
        """Return recent runtime events."""
        return self.sink.list_events(limit=limit, session_id=session_id, turn_id=turn_id)

    def summary(self) -> dict[str, Any]:
        """Return coarse operational metrics for dashboards and health checks."""
        events = self.list_events(limit=1000)
        counts: dict[str, int] = {}
        total_latency_ms = 0.0
        latency_count = 0
        tool_failures = 0
        model_calls = 0
        usage: dict[str, int] = {}
        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
            if event.level == "error" or event.event_type.endswith(".failed"):
                tool_failures += 1
            latency = event.payload.get("latency_ms")
            if isinstance(latency, (int, float)):
                total_latency_ms += float(latency)
                latency_count += 1
            if event.event_type == "model.completed":
                model_calls += 1
                raw_usage = event.payload.get("usage")
                if isinstance(raw_usage, dict):
                    for key, value in raw_usage.items():
                        if isinstance(value, int):
                            usage[key] = usage.get(key, 0) + value
        return {
            "event_count": len(events),
            "counts": counts,
            "turns_started": counts.get("turn.started", 0),
            "turns_completed": counts.get("turn.completed", 0),
            "tool_calls": counts.get("tool.completed", 0) + counts.get("tool.failed", 0),
            "failures": tool_failures,
            "model_calls": model_calls,
            "usage": usage,
            "estimated_cost_usd": None,
            "average_latency_ms": round(total_latency_ms / latency_count, 2)
            if latency_count
            else 0,
            "latest_event_at": events[-1].created_at.isoformat() if events else None,
        }


def build_observability_from_settings(settings: Any) -> ObservabilityManager:
    """Build observability using configured persistence."""
    backend = getattr(settings.memory, "observability_backend", "memory")
    if backend == "sqlite":
        return ObservabilityManager(SQLiteObservabilitySink(settings.memory.state_db_path))
    return ObservabilityManager()


def _row_to_event(row: sqlite3.Row) -> RuntimeEvent:
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return RuntimeEvent(
        id=row["id"],
        event_type=row["event_type"],
        level=row["level"],
        session_id=row["session_id"],
        turn_id=row["turn_id"],
        message=row["message"] or "",
        payload=payload,
        created_at=created_at,
    )
