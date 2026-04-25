from __future__ import annotations

"""Memory management primitives for PowerClaw."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from powerclaw.config.settings import PowerClawSettings
from powerclaw.runtime.state import MessageRecord


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for memory records."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MemoryItem:
    """A single transcript or retrieval memory record."""

    kind: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class MemoryQuery:
    """A retrieval request into the PowerClaw memory layer."""

    text: str
    limit: int = 5
    kinds: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryBackend(Protocol):
    """Backend contract shared by transcript and retrieval stores."""

    def append(self, item: MemoryItem) -> None:
        ...

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        ...

    def list_items(self) -> list[MemoryItem]:
        ...


class InMemoryBackend:
    """Simple backend used by the scaffold until persistent backends land."""

    def __init__(self) -> None:
        self._items: list[MemoryItem] = []

    def append(self, item: MemoryItem) -> None:
        self._items.append(item)

    def search(self, query: MemoryQuery) -> list[MemoryItem]:
        text = query.text.strip().lower()
        results = []
        for item in self._items:
            if query.kinds and item.kind not in query.kinds:
                continue
            if text and text not in item.content.lower():
                continue
            results.append(item)
            if len(results) >= query.limit:
                break
        return results

    def list_items(self) -> list[MemoryItem]:
        return list(self._items)


class MemoryManager:
    """Unifies transcript storage and retrieval-oriented memory under one interface."""

    def __init__(
        self,
        transcript_backend: MemoryBackend | None = None,
        retrieval_backend: MemoryBackend | None = None,
    ) -> None:
        self._transcript_backend = transcript_backend or InMemoryBackend()
        self._retrieval_backend = retrieval_backend or InMemoryBackend()

    def remember_message(
        self,
        message: MessageRecord,
        *,
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """Persist a runtime message into transcript memory."""
        metadata = {"role": message.role, **message.metadata}
        if session_id:
            metadata["session_id"] = session_id
        if turn_id:
            metadata["turn_id"] = turn_id
        self._transcript_backend.append(
            MemoryItem(
                kind=f"message:{message.role}",
                content=message.content,
                metadata=metadata,
            )
        )

    def record_fact(self, content: str, *, metadata: dict[str, Any] | None = None) -> MemoryItem:
        """Persist a retrieval-oriented fact or summary."""
        item = MemoryItem(kind="fact", content=content, metadata=metadata or {})
        self._retrieval_backend.append(item)
        return item

    def search(self, text: str, *, limit: int = 5) -> list[MemoryItem]:
        """Search retrieval memory first, then transcripts as a fallback."""
        query = MemoryQuery(text=text, limit=limit)
        results = self._retrieval_backend.search(query)
        if results:
            return results
        return self._transcript_backend.search(query)

    def transcript(self) -> list[MemoryItem]:
        """Return the stored transcript-oriented memory items."""
        return self._transcript_backend.list_items()


def build_memory_manager_from_settings(settings: PowerClawSettings) -> MemoryManager:
    """Build a memory manager using configured backend choices."""
    transcript_backend: MemoryBackend | None = None
    retrieval_backend: MemoryBackend | None = None

    if settings.memory.transcript_backend == "sqlite":
        from powerclaw.memory.sqlite import SQLiteMemoryBackend

        transcript_backend = SQLiteMemoryBackend(settings.memory.state_db_path)
    if settings.memory.retrieval_backend == "sqlite":
        from powerclaw.memory.sqlite import SQLiteMemoryBackend

        retrieval_backend = SQLiteMemoryBackend(settings.memory.state_db_path)
    return MemoryManager(
        transcript_backend=transcript_backend,
        retrieval_backend=retrieval_backend,
    )
