"""Provider abstraction and model routing surfaces for PowerClaw."""

from powerclaw.models.fake import ScriptedModelProvider, fake_tool_call
from powerclaw.models.openai_compatible import (
    OpenAICompatibleProvider,
    build_model_router_from_settings,
)
from powerclaw.models.router import (
    ModelProviderDiagnostic,
    ModelRequest,
    ModelResponse,
    ModelRouter,
    ModelToolCall,
)

__all__ = [
    "ModelRequest",
    "ModelProviderDiagnostic",
    "ModelResponse",
    "ModelRouter",
    "ModelToolCall",
    "OpenAICompatibleProvider",
    "ScriptedModelProvider",
    "build_model_router_from_settings",
    "fake_tool_call",
]
