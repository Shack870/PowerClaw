from __future__ import annotations

"""OpenAI-compatible chat-completions provider for PowerClaw."""

from collections.abc import Callable, Mapping
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from powerclaw.config.settings import DEFAULT_OPENAI_BASE_URL, PowerClawSettings
from powerclaw.models.router import ModelRequest, ModelResponse, ModelRouter, ModelToolCall
from powerclaw.runtime.state import MessageRecord

UrlOpen = Callable[..., Any]


class OpenAICompatibleProvider:
    """Small stdlib-backed adapter for OpenAI-compatible chat-completion APIs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        timeout_seconds: float = 120.0,
        opener: UrlOpen = urlopen,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Send one model request through an OpenAI-compatible HTTP endpoint."""
        model = request.preferred_model or "gpt-5.4"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [_message_to_chat_payload(message) for message in request.messages],
        }
        if request.tools:
            payload["tools"] = list(request.tools)

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        http_request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with self._opener(http_request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"model provider HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"model provider connection failed: {exc.reason}") from exc

        return _parse_chat_completion(raw, fallback_model=model)


def build_model_router_from_settings(
    settings: PowerClawSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> ModelRouter:
    """Build the default model router for a local PowerClaw runtime."""
    env = dict(os.environ if environ is None else environ)
    router = ModelRouter(default_model=settings.models.default_model)
    provider_name = settings.models.default_provider

    if provider_name == "openai":
        api_key = env.get("POWERCLAW_OPENAI_API_KEY") or env.get("OPENAI_API_KEY")
        base_url = settings.models.openai_base_url
        if api_key or base_url != DEFAULT_OPENAI_BASE_URL:
            router.register_provider(
                "openai",
                OpenAICompatibleProvider(
                    api_key=api_key,
                    base_url=base_url,
                    timeout_seconds=settings.models.request_timeout_seconds,
                ),
                metadata={"base_url": base_url, "api_key_configured": bool(api_key)},
            )
        else:
            router.register_unavailable_provider(
                "openai",
                (
                    "set POWERCLAW_OPENAI_API_KEY or OPENAI_API_KEY, or configure "
                    "POWERCLAW_OPENAI_BASE_URL for a local OpenAI-compatible endpoint"
                ),
                metadata={"base_url": base_url, "api_key_configured": False},
            )
    else:
        router.register_unavailable_provider(
            provider_name,
            "unsupported provider; currently supported provider ids: openai",
            metadata={"supported_providers": ["openai"]},
        )
    return router


def _message_to_chat_payload(message: MessageRecord) -> dict[str, Any]:
    """Convert PowerClaw messages to OpenAI-compatible chat messages."""
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.metadata.get("tool_call_id") or message.name or "tool-call",
            "content": message.content,
        }

    payload: dict[str, Any] = {
        "role": message.role,
        "content": message.content,
    }
    if message.role == "assistant" and message.metadata.get("tool_calls"):
        payload["tool_calls"] = [
            _tool_call_to_chat_payload(tool_call) for tool_call in message.metadata["tool_calls"]
        ]
    if message.name and message.role != "system":
        payload["name"] = message.name
    return payload


def _tool_call_to_chat_payload(tool_call: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a normalized PowerClaw tool-call dict to chat-completions shape."""
    arguments = tool_call.get("arguments") or {}
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments, ensure_ascii=False)
    return {
        "id": tool_call.get("id") or tool_call.get("call_id") or "tool-call",
        "type": "function",
        "function": {
            "name": tool_call.get("name") or "",
            "arguments": arguments,
        },
    }


def _parse_chat_completion(raw: Mapping[str, Any], *, fallback_model: str) -> ModelResponse:
    """Parse a chat-completions payload into PowerClaw's provider-neutral response."""
    choices = raw.get("choices") or []
    message = choices[0].get("message", {}) if choices else {}
    content = message.get("content") or ""
    tool_calls = [_parse_tool_call(tool_call) for tool_call in message.get("tool_calls") or []]
    return ModelResponse(
        model=str(raw.get("model") or fallback_model),
        content=content,
        tool_calls=tool_calls,
        raw=dict(raw),
    )


def _parse_tool_call(raw_tool_call: Mapping[str, Any]) -> ModelToolCall:
    """Parse one OpenAI-compatible tool-call object."""
    function = raw_tool_call.get("function") or {}
    arguments_raw = function.get("arguments") or "{}"
    try:
        arguments = json.loads(arguments_raw)
    except json.JSONDecodeError:
        arguments = {"_raw": arguments_raw}
    if not isinstance(arguments, dict):
        arguments = {"value": arguments}
    return ModelToolCall(
        name=str(function.get("name") or ""),
        arguments=arguments,
        call_id=raw_tool_call.get("id"),
    )
