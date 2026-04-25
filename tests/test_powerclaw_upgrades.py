from __future__ import annotations

import json

from powerclaw.cli import build_default_agent
from powerclaw.config import MemorySettings, ModelSettings, PowerClawSettings, RuntimeSettings
from powerclaw.models import ModelResponse, ModelRouter, ScriptedModelProvider, fake_tool_call
from powerclaw.permissions import PermissionManager, SQLitePermissionStore
from powerclaw.runtime.store import SQLiteStateStore
from powerclaw.skills import FileSkillProvider, SkillEngine
from powerclaw.tools import ToolExecutionContext, ToolRegistry, register_skill_tools, register_terminal_tool
from powerclaw.workflows.repo_operator import REPO_OPERATOR_SKILL_ID, run_repo_operator_workflow


def test_sqlite_state_store_restores_full_session(tmp_path) -> None:
    settings = PowerClawSettings(
        memory=MemorySettings(
            session_backend="sqlite",
            transcript_backend="sqlite",
            observability_backend="sqlite",
            state_db_path=tmp_path / "state.db",
        ),
        runtime=RuntimeSettings(enable_reflection=False),
    ).with_workspace(tmp_path)
    first = build_default_agent(
        settings=settings,
        include_provider=False,
        include_readonly_tools=False,
        include_skill_tools=False,
    )

    session = first.create_session(session_id="session-1", platform="test")
    first.run_turn(session, "persist this")

    second_store = SQLiteStateStore(tmp_path / "state.db")
    restored = second_store.load_session("session-1")

    assert restored is not None
    assert restored.session_id == "session-1"
    assert [message.role for message in restored.history] == ["user", "assistant"]
    assert restored.turns[0].messages[0].content == "persist this"
    assert restored.turns[0].metadata["latency_ms"] >= 0


def test_learn_procedure_creates_reusable_workspace_skill(tmp_path) -> None:
    skills = SkillEngine([FileSkillProvider()])
    registry = ToolRegistry()
    register_skill_tools(registry, skills)
    context = ToolExecutionContext(
        session=build_default_agent(include_provider=False).create_session(),
        working_directory=str(tmp_path),
        allowed_tool_names=("learn_procedure", "list_skills"),
        enforce_tool_allowlist=True,
    )

    result = registry.invoke(
        "learn_procedure",
        {
            "title": "Ship EC2 Patch",
            "summary": "Prepare and verify an EC2-ready patch.",
            "steps": ["Inspect files", "Run tests", "Package deployment"],
            "tags": ["ec2", "release"],
        },
        context,
    )
    payload = json.loads(result.content)
    listed = registry.invoke("list_skills", {}, context)
    listed_payload = json.loads(listed.content)

    assert result.ok is True
    assert payload["skill"]["skill_id"] == "ship-ec2-patch"
    assert (tmp_path / ".powerclaw" / "skills" / "ship-ec2-patch" / "SKILL.md").exists()
    assert any(skill["skill_id"] == "ship-ec2-patch" for skill in listed_payload["skills"])
    activation = skills.activate("ship-ec2-patch", workspace_dir=tmp_path)
    assert activation is not None
    assert "Run tests" in activation.prompt_fragment


def test_permission_manager_persists_terminal_approval(tmp_path) -> None:
    manager = PermissionManager(SQLitePermissionStore(tmp_path / "state.db"))
    request = manager.request_permission(
        kind="terminal.command",
        subject="echo ok",
        session_id="session-1",
        reason="test",
    )

    assert manager.is_approved(
        kind="terminal.command",
        subject="echo ok",
        session_id="session-1",
    ) is False

    manager.approve(request.id)
    reloaded = PermissionManager(SQLitePermissionStore(tmp_path / "state.db"))

    assert reloaded.is_approved(
        kind="terminal.command",
        subject="echo ok",
        session_id="session-1",
    ) is True


def test_runtime_records_observability_events_and_permission_requests(tmp_path) -> None:
    registry = ToolRegistry()
    register_terminal_tool(registry)
    provider = ScriptedModelProvider(
        [
            ModelResponse(
                model="fake-model",
                tool_calls=[fake_tool_call("terminal", {"command": "echo pending"}, call_id="t1")],
            ),
            ModelResponse(model="fake-model", content="Waiting on approval."),
        ]
    )
    router = ModelRouter(default_model="fake-model")
    router.register_provider("fake", provider)
    settings = PowerClawSettings(
        memory=MemorySettings(
            permissions_backend="sqlite",
            observability_backend="sqlite",
            state_db_path=tmp_path / "state.db",
        ),
        runtime=RuntimeSettings(
            workspace_dir=tmp_path,
            terminal_enabled=True,
            enable_reflection=False,
        ),
    )
    agent = build_default_agent(
        settings=settings,
        include_provider=False,
        include_readonly_tools=False,
        include_skill_tools=False,
    )
    agent.dependencies.tools = registry
    agent.dependencies.models = router
    agent.settings = PowerClawSettings(
        memory=settings.memory,
        runtime=settings.runtime,
        models=ModelSettings(default_provider="fake", default_model="fake-model"),
    )

    turn = agent.run_turn(agent.create_session(session_id="s1"), "try terminal")
    events = agent.dependencies.observability.list_events(limit=50)
    requests = agent.dependencies.permissions.list_requests(status="pending")

    assert json.loads(turn.messages[2].content)["status"] == "approval_required"
    assert any(event.event_type == "permission.requested" for event in events)
    assert any(event.event_type == "turn.completed" for event in events)
    assert requests[0].subject == "echo pending"
    assert agent.dependencies.observability.summary()["tool_calls"] == 1


def test_repo_operator_workflow_activates_flagship_skill(tmp_path) -> None:
    settings = PowerClawSettings(runtime=RuntimeSettings(enable_reflection=False)).with_workspace(tmp_path)
    agent = build_default_agent(
        settings=settings,
        include_provider=False,
        include_readonly_tools=False,
        include_skill_tools=True,
    )
    session = agent.create_session(platform="test")

    turn = run_repo_operator_workflow(agent, session, objective="Prepare EC2 packaging.")

    assert REPO_OPERATOR_SKILL_ID in session.active_skill_ids
    assert turn.metadata["active_skills"] == [REPO_OPERATOR_SKILL_ID]
    assert "no model provider is configured" in turn.messages[-1].content
