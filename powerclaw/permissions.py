from __future__ import annotations

"""Human approval and permission primitives for PowerClaw."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Any, Protocol


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for permission records."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class PermissionRequest:
    """A pending or resolved request for a stronger runtime capability."""

    id: str
    kind: str
    subject: str
    status: str = "pending"
    session_id: str | None = None
    turn_id: str | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    requested_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable permission payload."""
        return {
            "id": self.id,
            "kind": self.kind,
            "subject": self.subject,
            "status": self.status,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "reason": self.reason,
            "metadata": dict(self.metadata),
            "requested_at": self.requested_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
        }


class PermissionStore(Protocol):
    """Storage contract for approval requests."""

    def create(self, request: PermissionRequest) -> PermissionRequest:
        ...

    def get(self, request_id: str) -> PermissionRequest | None:
        ...

    def find(
        self,
        *,
        kind: str | None = None,
        subject: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[PermissionRequest]:
        ...

    def update(self, request: PermissionRequest) -> PermissionRequest:
        ...


class InMemoryPermissionStore:
    """In-process permission store used for local tests and non-durable runs."""

    def __init__(self) -> None:
        self._requests: dict[str, PermissionRequest] = {}
        self._lock = threading.Lock()

    def create(self, request: PermissionRequest) -> PermissionRequest:
        with self._lock:
            self._requests[request.id] = request
        return request

    def get(self, request_id: str) -> PermissionRequest | None:
        with self._lock:
            return self._requests.get(request_id)

    def find(
        self,
        *,
        kind: str | None = None,
        subject: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[PermissionRequest]:
        with self._lock:
            requests = list(self._requests.values())
        return [
            request
            for request in requests
            if (kind is None or request.kind == kind)
            and (subject is None or request.subject == subject)
            and (session_id is None or request.session_id == session_id)
            and (status is None or request.status == status)
        ]

    def update(self, request: PermissionRequest) -> PermissionRequest:
        with self._lock:
            self._requests[request.id] = request
        return request


class SQLitePermissionStore:
    """SQLite-backed permission store shared with PowerClaw state."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def create(self, request: PermissionRequest) -> PermissionRequest:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO permission_requests (
                    id, kind, subject, status, session_id, turn_id, reason,
                    metadata_json, requested_at, resolved_at, resolved_by, resolution_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _request_row(request),
            )
            self._conn.commit()
        return request

    def get(self, request_id: str) -> PermissionRequest | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM permission_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        return _row_to_request(row) if row else None

    def find(
        self,
        *,
        kind: str | None = None,
        subject: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[PermissionRequest]:
        clauses = []
        params: list[object] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if subject is not None:
            clauses.append("subject = ?")
            params.append(subject)
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM permission_requests {where} ORDER BY requested_at DESC",
                params,
            ).fetchall()
        return [_row_to_request(row) for row in rows]

    def update(self, request: PermissionRequest) -> PermissionRequest:
        return self.create(request)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS permission_requests (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL,
                    session_id TEXT,
                    turn_id TEXT,
                    reason TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    requested_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    resolution_note TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_permission_requests_lookup
                    ON permission_requests(kind, subject, session_id, status);
                CREATE INDEX IF NOT EXISTS idx_permission_requests_status
                    ON permission_requests(status, requested_at);
                """
            )
            self._conn.commit()


class PermissionManager:
    """Coordinates approval requests and exact-subject permission checks."""

    def __init__(self, store: PermissionStore | None = None) -> None:
        self.store = store or InMemoryPermissionStore()

    def request_permission(
        self,
        *,
        kind: str,
        subject: str,
        session_id: str | None = None,
        turn_id: str | None = None,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PermissionRequest:
        """Create or return an existing pending request for the same capability."""
        existing = self.store.find(
            kind=kind,
            subject=subject,
            session_id=session_id,
            status="pending",
        )
        if existing:
            return existing[0]

        request = PermissionRequest(
            id=str(uuid.uuid4()),
            kind=kind,
            subject=subject,
            session_id=session_id,
            turn_id=turn_id,
            reason=reason,
            metadata=metadata or {},
        )
        return self.store.create(request)

    def is_approved(
        self,
        *,
        kind: str,
        subject: str,
        session_id: str | None = None,
    ) -> bool:
        """Return whether this exact subject was approved for the session or globally."""
        session_matches = self.store.find(
            kind=kind,
            subject=subject,
            session_id=session_id,
            status="approved",
        )
        if session_matches:
            return True
        global_matches = self.store.find(
            kind=kind,
            subject=subject,
            session_id=None,
            status="approved",
        )
        return bool(global_matches)

    def list_requests(self, *, status: str | None = None) -> list[PermissionRequest]:
        """List permission requests, optionally filtered by status."""
        return self.store.find(status=status)

    def approve(
        self,
        request_id: str,
        *,
        resolved_by: str = "operator",
        note: str | None = None,
    ) -> PermissionRequest:
        """Approve a pending request."""
        request = self._require_request(request_id)
        request.status = "approved"
        request.resolved_at = utc_now()
        request.resolved_by = resolved_by
        request.resolution_note = note
        return self.store.update(request)

    def deny(
        self,
        request_id: str,
        *,
        resolved_by: str = "operator",
        note: str | None = None,
    ) -> PermissionRequest:
        """Deny a pending request."""
        request = self._require_request(request_id)
        request.status = "denied"
        request.resolved_at = utc_now()
        request.resolved_by = resolved_by
        request.resolution_note = note
        return self.store.update(request)

    def _require_request(self, request_id: str) -> PermissionRequest:
        request = self.store.get(request_id)
        if request is None:
            raise KeyError(f"unknown permission request: {request_id}")
        return request


def build_permission_manager_from_settings(settings: Any) -> PermissionManager:
    """Build a permission manager using configured persistence."""
    backend = getattr(settings.memory, "permissions_backend", "memory")
    if backend == "sqlite":
        return PermissionManager(SQLitePermissionStore(settings.memory.state_db_path))
    return PermissionManager()


def _request_row(request: PermissionRequest) -> tuple[object, ...]:
    return (
        request.id,
        request.kind,
        request.subject,
        request.status,
        request.session_id,
        request.turn_id,
        request.reason,
        json.dumps(request.metadata, ensure_ascii=False),
        request.requested_at.astimezone(timezone.utc).isoformat(),
        request.resolved_at.astimezone(timezone.utc).isoformat()
        if request.resolved_at
        else None,
        request.resolved_by,
        request.resolution_note,
    )


def _row_to_request(row: sqlite3.Row) -> PermissionRequest:
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    requested_at = _parse_datetime(row["requested_at"])
    resolved_at = _parse_datetime(row["resolved_at"]) if row["resolved_at"] else None
    return PermissionRequest(
        id=row["id"],
        kind=row["kind"],
        subject=row["subject"],
        status=row["status"],
        session_id=row["session_id"],
        turn_id=row["turn_id"],
        reason=row["reason"] or "",
        metadata=metadata,
        requested_at=requested_at,
        resolved_at=resolved_at,
        resolved_by=row["resolved_by"],
        resolution_note=row["resolution_note"],
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
