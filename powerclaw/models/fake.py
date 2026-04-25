from __future__ import annotations

"""Deterministic model providers for tests and local runtime smoke checks."""

from collections import deque
from collections.abc import Sequence

from powerclaw.models.router import ModelRequest, ModelResponse, ModelToolCall


class ScriptedModelProvider:
    """Return pre-seeded model responses in order.

    This provider gives PowerClaw tests a deterministic model loop without
    network access or provider credentials. Each request is retained so tests can
    assert which messages and tools the runtime sent to the provider.
    """

    def __init__(
        self,
        responses: Sequence[ModelResponse | str],
        *,
        default_model: str = "fake-model",
        exhausted_content: str = "",
    ) -> None:
        self.default_model = default_model
        self.exhausted_content = exhausted_content
        self.requests: list[ModelRequest] = []
        self._responses: deque[ModelResponse | str] = deque(responses)

    def generate(self, request: ModelRequest) -> ModelResponse:
        """Return the next scripted response and record the incoming request."""
        self.requests.append(request)
        if not self._responses:
            return ModelResponse(model=request.preferred_model or self.default_model, content=self.exhausted_content)

        response = self._responses.popleft()
        if isinstance(response, str):
            return ModelResponse(model=request.preferred_model or self.default_model, content=response)
        return response


def fake_tool_call(name: str, arguments: dict | None = None, *, call_id: str | None = None) -> ModelToolCall:
    """Create a normalized fake tool call for tests."""
    return ModelToolCall(name=name, arguments=arguments or {}, call_id=call_id)
