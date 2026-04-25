from __future__ import annotations

"""Reflection and compaction hooks for the PowerClaw runtime."""

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from powerclaw.runtime.state import SessionState, TurnRecord


@dataclass(slots=True)
class ReflectionNote:
    """A structured note emitted by a post-turn reflection pass."""

    kind: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable note payload."""
        return {
            "kind": self.kind,
            "summary": self.summary,
            "metadata": dict(self.metadata),
        }


class ReflectionHook(Protocol):
    """Hook contract used by reflection and compaction passes."""

    def after_turn(self, session: SessionState, turn: TurnRecord) -> Sequence[ReflectionNote]:
        ...


class ReflectionEngine:
    """Collects reflection hooks behind a PowerClaw-owned interface."""

    def __init__(self, hooks: Sequence[ReflectionHook] | None = None) -> None:
        self._hooks: list[ReflectionHook] = list(hooks or [])

    def register_hook(self, hook: ReflectionHook) -> None:
        """Attach a reflection hook to the runtime."""
        self._hooks.append(hook)

    def after_turn(self, session: SessionState, turn: TurnRecord) -> list[ReflectionNote]:
        """Run all registered reflection hooks for a completed turn."""
        notes: list[ReflectionNote] = []
        for hook in self._hooks:
            notes.extend(hook.after_turn(session, turn))
        return notes


class TurnSummaryReflectionHook:
    """Emit a compact, structured summary for completed turns."""

    def after_turn(self, session: SessionState, turn: TurnRecord) -> Sequence[ReflectionNote]:
        final_message = next(
            (message for message in reversed(turn.messages) if message.role == "assistant"),
            None,
        )
        status = str(turn.metadata.get("error") or turn.metadata.get("status") or "completed")
        summary = (
            f"Turn {turn.id} on {session.platform} {status} with "
            f"{len(turn.messages)} messages and {len(turn.tool_calls)} tool calls."
        )
        metadata = {
            "session_id": session.session_id,
            "turn_id": turn.id,
            "platform": session.platform,
            "message_count": len(turn.messages),
            "tool_call_count": len(turn.tool_calls),
            "final_assistant_preview": _preview(final_message.content if final_message else ""),
        }
        return [ReflectionNote(kind="turn_summary", summary=summary, metadata=metadata)]


class DurableFactCandidateHook:
    """Suggest durable facts without writing memory automatically."""

    def after_turn(self, session: SessionState, turn: TurnRecord) -> Sequence[ReflectionNote]:
        notes: list[ReflectionNote] = []
        for message in turn.messages:
            if message.role != "user":
                continue
            candidate = _fact_candidate(message.content)
            if not candidate:
                continue
            notes.append(
                ReflectionNote(
                    kind="memory_candidate",
                    summary=f"Possible durable fact from user: {candidate}",
                    metadata={
                        "session_id": session.session_id,
                        "turn_id": turn.id,
                        "source_role": "user",
                    },
                )
            )
        return notes


def build_default_reflection_engine() -> ReflectionEngine:
    """Build PowerClaw's default non-mutating reflection pipeline."""
    return ReflectionEngine([TurnSummaryReflectionHook(), DurableFactCandidateHook()])


def _fact_candidate(content: str) -> str | None:
    normalized = " ".join(content.strip().split())
    if not normalized:
        return None
    lower = normalized.lower()
    durable_prefixes = (
        "remember ",
        "please remember ",
        "my ",
        "i prefer ",
        "i like ",
        "i use ",
    )
    if lower.startswith(durable_prefixes):
        return _preview(normalized, limit=240)
    return None


def _preview(content: str, *, limit: int = 160) -> str:
    normalized = " ".join(content.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."
