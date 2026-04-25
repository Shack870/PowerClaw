from __future__ import annotations

import json

from powerclaw.config import ModelSettings, PowerClawSettings
from powerclaw.models.openai_compatible import OpenAICompatibleProvider, build_model_router_from_settings
from powerclaw.models.router import ModelRequest
from powerclaw.runtime.state import MessageRecord


class FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_openai_provider_sends_chat_completion_payload_and_parses_tool_call() -> None:
    captured = {}

    def fake_opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHttpResponse(
            {
                "model": "gpt-test",
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": "{\"path\":\"README.md\"}",
                                    },
                                }
                            ],
                        }
                    }
                ],
            }
        )

    provider = OpenAICompatibleProvider(
        api_key="test-key",
        base_url="https://models.example/v1",
        timeout_seconds=7,
        opener=fake_opener,
    )

    response = provider.generate(
        ModelRequest(
            messages=[MessageRecord(role="user", content="Read the README")],
            preferred_model="gpt-test",
            tools=[{"type": "function", "function": {"name": "read_file"}}],
        )
    )

    assert captured["url"] == "https://models.example/v1/chat/completions"
    assert captured["timeout"] == 7
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "Read the README"}]
    assert captured["payload"]["tools"][0]["function"]["name"] == "read_file"
    assert response.model == "gpt-test"
    assert response.content == ""
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "README.md"}
    assert response.tool_calls[0].call_id == "call-1"


def test_openai_provider_preserves_assistant_tool_call_history() -> None:
    captured = {}

    def fake_opener(request, timeout):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeHttpResponse({"model": "gpt-test", "choices": [{"message": {"content": "Done"}}]})

    provider = OpenAICompatibleProvider(base_url="http://localhost:9999/v1", opener=fake_opener)
    provider.generate(
        ModelRequest(
            messages=[
                MessageRecord(
                    role="assistant",
                    content="",
                    metadata={
                        "tool_calls": [
                            {"id": "call-1", "name": "read_file", "arguments": {"path": "a.txt"}}
                        ]
                    },
                ),
                MessageRecord(
                    role="tool",
                    content="{\"content\":\"hello\"}",
                    name="read_file",
                    metadata={"tool_call_id": "call-1"},
                ),
            ],
            preferred_model="gpt-test",
        )
    )

    messages = captured["payload"]["messages"]
    assert messages[0]["tool_calls"][0]["id"] == "call-1"
    assert messages[0]["tool_calls"][0]["function"]["arguments"] == "{\"path\": \"a.txt\"}"
    assert messages[1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": "{\"content\":\"hello\"}",
    }


def test_model_router_from_settings_reports_missing_openai_credentials() -> None:
    router = build_model_router_from_settings(PowerClawSettings(), environ={})

    assert router.has_providers() is False
    assert router.diagnostics()[0].name == "openai"
    assert router.diagnostics()[0].available is False
    assert "POWERCLAW_OPENAI_API_KEY" in router.diagnostics()[0].reason


def test_model_router_from_settings_reports_unsupported_provider() -> None:
    settings = PowerClawSettings(models=ModelSettings(default_provider="local"))

    router = build_model_router_from_settings(settings, environ={})

    assert router.has_providers() is False
    assert router.diagnostics()[0].name == "local"
    assert "unsupported provider" in router.diagnostics()[0].reason
