from __future__ import annotations

import json

from powerclaw import PowerClawAgent
from powerclaw.config import ModelSettings, PowerClawSettings, RuntimeSettings
from powerclaw.models import ModelResponse, ModelRouter, ScriptedModelProvider, fake_tool_call
from powerclaw.tools import ToolExecutionContext, ToolRegistry


def test_no_provider_turn_returns_scaffold_response() -> None:
    agent = PowerClawAgent()
    session = agent.create_session(platform="local")

    turn = agent.run_turn(session, "hello")

    assert turn.messages[-1].role == "assistant"
    assert turn.messages[-1].metadata["status"] == "scaffold"
    assert "no model provider is configured" in turn.messages[-1].content
    assert "Provider diagnostics" in turn.messages[-1].content
    assert turn.metadata["available_tools"] == []
    assert [item.kind for item in agent.dependencies.memory.transcript()] == [
        "message:user",
        "message:assistant",
    ]


def test_runtime_executes_allowed_tool_call_and_continues_model_loop() -> None:
    tools = ToolRegistry()
    tools.register_function(
        name="echo",
        description="Echo input text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=lambda args, context: {"echo": args["text"], "session": context.session.session_id},
    )

    provider = ScriptedModelProvider(
        [
            ModelResponse(
                model="fake-model",
                content="I need the echo tool.",
                tool_calls=[fake_tool_call("echo", {"text": "hello"}, call_id="call-1")],
            ),
            ModelResponse(model="fake-model", content="Done."),
        ]
    )
    router = ModelRouter(default_model="fake-model")
    router.register_provider("fake", provider)
    settings = PowerClawSettings(
        runtime=RuntimeSettings(enable_reflection=False),
        models=ModelSettings(default_provider="fake", default_model="fake-model"),
    )

    agent = PowerClawAgent(settings=settings, tool_registry=tools, model_router=router)
    session = agent.create_session(platform="local")

    turn = agent.run_turn(session, "use a tool")

    assert turn.metadata["iterations"] == 2
    assert turn.metadata["tool_definition_count"] == 1
    assert len(provider.requests) == 2
    assert provider.requests[0].tools[0]["function"]["name"] == "echo"
    assert turn.tool_calls[0].status == "completed"
    assert json.loads(turn.tool_calls[0].result)["echo"] == "hello"
    assert [message.role for message in turn.messages] == ["user", "assistant", "tool", "assistant"]
    assert turn.messages[-1].content == "Done."


def test_runtime_tells_model_when_terminal_is_trusted(tmp_path) -> None:
    provider = ScriptedModelProvider([ModelResponse(model="fake-model", content="Done.")])
    router = ModelRouter(default_model="fake-model")
    router.register_provider("fake", provider)
    settings = PowerClawSettings(
        runtime=RuntimeSettings(
            workspace_dir=tmp_path,
            terminal_enabled=True,
            terminal_trusted=True,
            enable_reflection=False,
        ),
        models=ModelSettings(default_provider="fake", default_model="fake-model"),
    )

    agent = PowerClawAgent(settings=settings, model_router=router)
    agent.run_turn(agent.create_session(platform="http"), "create a desktop file")

    system_messages = [
        message.content for message in provider.requests[0].messages if message.role == "system"
    ]
    assert any("Trusted terminal mode is enabled" in message for message in system_messages)
    assert any("Desktop" in message for message in system_messages)


def test_runtime_blocks_registered_tool_not_in_active_toolset() -> None:
    tools = ToolRegistry()
    called = False

    def secret_handler(args, context):
        nonlocal called
        called = True
        return {"should_not_run": True}

    tools.register_function(
        name="secret",
        description="A disabled tool.",
        toolset="disabled",
        handler=secret_handler,
    )

    provider = ScriptedModelProvider(
        [
            ModelResponse(
                model="fake-model",
                tool_calls=[fake_tool_call("secret", {}, call_id="call-secret")],
            ),
            ModelResponse(model="fake-model", content="Recovered."),
        ]
    )
    router = ModelRouter(default_model="fake-model")
    router.register_provider("fake", provider)
    settings = PowerClawSettings(
        runtime=RuntimeSettings(enabled_toolsets=("core",), enable_reflection=False),
        models=ModelSettings(default_provider="fake", default_model="fake-model"),
    )

    agent = PowerClawAgent(settings=settings, tool_registry=tools, model_router=router)
    session = agent.create_session(platform="local")

    turn = agent.run_turn(session, "try disabled tool")

    assert called is False
    assert turn.metadata["available_tools"] == []
    assert turn.tool_calls[0].status == "failed"
    assert turn.tool_calls[0].metadata["error"] == "tool not allowed"
    assert json.loads(turn.messages[2].content)["error"] == "tool not allowed for this turn: secret"
    assert turn.messages[-1].content == "Recovered."


def test_registry_allows_direct_invocation_when_no_allowlist_is_enforced() -> None:
    tools = ToolRegistry()
    tools.register_function(name="ping", description="Ping.", handler=lambda args, context: "pong")
    agent = PowerClawAgent(tool_registry=tools)
    session = agent.create_session()
    context = ToolExecutionContext(session=session)

    result = tools.invoke("ping", {}, context)

    assert result.ok is True
    assert result.content == "pong"


def test_model_router_fails_over_from_configured_provider() -> None:
    class FailingProvider:
        def generate(self, request):
            raise RuntimeError("primary down")

    fallback = ScriptedModelProvider([ModelResponse(model="fallback-model", content="Recovered.")])
    router = ModelRouter(default_model="fake-model")
    router.register_provider("primary", FailingProvider())
    router.register_provider("fallback", fallback)
    settings = PowerClawSettings(
        runtime=RuntimeSettings(enable_reflection=False),
        models=ModelSettings(
            default_provider="primary",
            default_model="fake-model",
            enable_failover=True,
        ),
    )
    agent = PowerClawAgent(settings=settings, model_router=router)

    turn = agent.run_turn(agent.create_session(), "use fallback")

    assert turn.messages[-1].content == "Recovered."
    assert len(fallback.requests) == 1


def test_model_router_reports_unavailable_provider_diagnostics() -> None:
    router = ModelRouter()
    router.register_unavailable_provider("openai", "missing API key")
    agent = PowerClawAgent(model_router=router)

    turn = agent.run_turn(agent.create_session(), "hello")

    diagnostics = turn.messages[-1].metadata["provider_diagnostics"]
    assert diagnostics == [
        {
            "name": "openai",
            "available": False,
            "reason": "missing API key",
            "metadata": {},
        }
    ]
    assert "openai unavailable: missing API key" in turn.messages[-1].content


def test_default_reflection_emits_summary_and_memory_candidate_without_writing_fact() -> None:
    settings = PowerClawSettings(runtime=RuntimeSettings(enable_reflection=True))
    agent = PowerClawAgent(settings=settings)
    session = agent.create_session(platform="local")

    turn = agent.run_turn(session, "Remember my deployment target is EC2.")

    assert any("messages" in note for note in turn.metadata["reflection_notes"])
    assert any("Possible durable fact" in note for note in turn.metadata["reflection_notes"])
    assert {note["kind"] for note in turn.metadata["reflection_note_details"]} == {
        "memory_candidate",
        "turn_summary",
    }
    assert agent.dependencies.memory.search("deployment target")[0].kind == "message:user"
