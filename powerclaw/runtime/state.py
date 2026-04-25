from __future__ import annotations

"""Canonical runtime state models for PowerClaw."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
import uuid

MessageRole = Literal["system", "user", "assistant", "tool"]


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for runtime records."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MessageRecord:
    """A normalized message stored in session history."""

    role: MessageRole
    content: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class ToolCallRecord:
    """A single tool invocation tracked within a turn."""

    tool_name: str
    call_id: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TurnRecord:
    """Represents one user-visible turn through the runtime loop."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_input: str = ""
    model: str | None = None
    messages: list[MessageRecord] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    def add_message(self, message: MessageRecord) -> None:
        """Attach a message emitted during the turn."""
        self.messages.append(message)

    def add_tool_call(self, tool_call: ToolCallRecord) -> None:
        """Attach a tool call emitted during the turn."""
        self.tool_calls.append(tool_call)

    def complete(self) -> None:
        """Mark the turn as finished."""
        self.completed_at = utc_now()


@dataclass(slots=True)
class SessionState:
    """The authoritative PowerClaw session and task state container."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str | None = None
    platform: str = "local"
    active_skill_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[MessageRecord] = field(default_factory=list)
    turns: list[TurnRecord] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(self) -> None:
        """Update the session timestamp after a state change."""
        self.updated_at = utc_now()

    def append_message(
        self,
        role: MessageRole,
        content: str,
        *,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        """Append a normalized message to the session history."""
        message = MessageRecord(role=role, content=content, name=name, metadata=metadata or {})
        self.history.append(message)
        self.touch()
        return message

    def start_turn(self, user_input: str, *, model: str | None = None) -> TurnRecord:
        """Create and register a new turn record."""
        turn = TurnRecord(user_input=user_input, model=model)
        self.turns.append(turn)
        self.touch()
        return turn
