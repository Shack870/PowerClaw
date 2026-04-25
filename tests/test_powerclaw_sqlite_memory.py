from __future__ import annotations

from powerclaw.memory import MemoryItem, MemoryQuery, SQLiteMemoryBackend


def test_sqlite_memory_backend_persists_items(tmp_path) -> None:
    db_path = tmp_path / "state.db"
    first = SQLiteMemoryBackend(db_path)
    first.append(MemoryItem(kind="message:user", content="hello durable world", metadata={"role": "user"}))
    first.close()

    second = SQLiteMemoryBackend(db_path)
    items = second.list_items()
    results = second.search(MemoryQuery(text="durable", limit=5))

    assert len(items) == 1
    assert items[0].kind == "message:user"
    assert items[0].metadata == {"role": "user"}
    assert results[0].content == "hello durable world"
    second.close()
