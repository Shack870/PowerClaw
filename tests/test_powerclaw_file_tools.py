from __future__ import annotations

import json

from powerclaw import PowerClawAgent
from powerclaw.tools import ToolExecutionContext, ToolRegistry, register_readonly_file_tools


def _tool_context(workspace) -> ToolExecutionContext:
    agent = PowerClawAgent()
    session = agent.create_session()
    return ToolExecutionContext(session=session, working_directory=str(workspace))


def test_readonly_file_tools_list_read_and_search_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("alpha\nBeta\n", encoding="utf-8")
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("print('alpha')\n", encoding="utf-8")

    registry = ToolRegistry()
    register_readonly_file_tools(registry)
    context = _tool_context(workspace)

    listed = json.loads(registry.invoke("list_workspace", {}, context).content)
    assert listed["path"] == "."
    assert [entry["path"] for entry in listed["entries"]] == ["src", "notes.txt"]

    read = json.loads(registry.invoke("read_file", {"path": "notes.txt"}, context).content)
    assert read["path"] == "notes.txt"
    assert read["content"] == "alpha\nBeta\n"
    assert read["truncated"] is False

    search = json.loads(
        registry.invoke("search_files", {"query": "alpha", "glob": "*.py"}, context).content
    )
    assert search["matches"] == [{"path": "src/app.py", "line": 1, "text": "print('alpha')"}]


def test_read_file_rejects_paths_outside_workspace(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    registry = ToolRegistry()
    register_readonly_file_tools(registry)
    context = _tool_context(workspace)

    result = registry.invoke("read_file", {"path": "../outside.txt"}, context)

    assert result.ok is False
    assert "path escapes workspace" in json.loads(result.content)["error"]
