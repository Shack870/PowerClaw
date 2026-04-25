from __future__ import annotations

import json
import sys

from powerclaw import PowerClawAgent
from powerclaw.config import ModelSettings, PowerClawSettings, RuntimeSettings
from powerclaw.models import ModelResponse, ModelRouter, ScriptedModelProvider, fake_tool_call
from powerclaw.tools import ToolExecutionContext, ToolRegistry, register_terminal_tool


def test_terminal_tool_denies_unapproved_command(tmp_path) -> None:
    registry = ToolRegistry()
    register_terminal_tool(registry)
    agent = PowerClawAgent(tool_registry=registry)
    context = ToolExecutionContext(
        session=agent.create_session(),
        working_directory=str(tmp_path),
        allowed_tool_names=("terminal",),
        enforce_tool_allowlist=True,
    )

    result = registry.invoke("terminal", {"command": "echo denied"}, context)
    payload = json.loads(result.content)

    assert result.ok is False
    assert result.error == "command was not explicitly approved"
    assert payload["status"] == "denied"
    assert payload["approved_commands"] == []


def test_terminal_tool_runs_exactly_approved_command(tmp_path) -> None:
    registry = ToolRegistry()
    register_terminal_tool(registry)
    command = f"{sys.executable} -c \"print('ok')\""
    agent = PowerClawAgent(tool_registry=registry)
    context = ToolExecutionContext(
        session=agent.create_session(),
        working_directory=str(tmp_path),
        allowed_tool_names=("terminal",),
        enforce_tool_allowlist=True,
        metadata={"terminal_allowed_commands": [command], "terminal_timeout_seconds": 5},
    )

    result = registry.invoke("terminal", {"command": command}, context)
    payload = json.loads(result.content)

    assert result.ok is True
    assert payload["status"] == "completed"
    assert payload["exit_code"] == 0
    assert payload["stdout"] == "ok\n"


def test_runtime_marks_denied_terminal_call_failed(tmp_path) -> None:
    registry = ToolRegistry()
    register_terminal_tool(registry)
    provider = ScriptedModelProvider(
        [
            ModelResponse(
                model="fake-model",
                tool_calls=[fake_tool_call("terminal", {"command": "echo denied"}, call_id="t1")],
            ),
            ModelResponse(model="fake-model", content="Denied as expected."),
        ]
    )
    router = ModelRouter(default_model="fake-model")
    router.register_provider("fake", provider)
    settings = PowerClawSettings(
        runtime=RuntimeSettings(
            workspace_dir=tmp_path,
            terminal_enabled=True,
            terminal_allowed_commands=(),
            enable_reflection=False,
        ),
        models=ModelSettings(default_provider="fake", default_model="fake-model"),
    )
    agent = PowerClawAgent(settings=settings, tool_registry=registry, model_router=router)

    turn = agent.run_turn(agent.create_session(), "try terminal")

    assert turn.tool_calls[0].status == "failed"
    assert turn.tool_calls[0].metadata["error"] == "operator approval is required before execution"
    payload = json.loads(turn.messages[2].content)
    assert payload["status"] == "approval_required"
    assert payload["approval_id"]
